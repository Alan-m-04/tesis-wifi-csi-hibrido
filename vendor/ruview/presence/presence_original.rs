pub const VARIANCE_SEPARATION_MARGIN: f32 = 0.05;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PresenceSpecialist {
    /// Decision threshold on series variance.
    pub threshold: f32,
    /// Occupied-anchor mean variance (for confidence scaling).
    pub occupied_var: f32,
    /// Empty-room mean of the scalar series (mean-shift reference).
    #[serde(default)]
    pub empty_mean: f32,
    /// |mean − empty_mean| beyond which the mean alone indicates presence.
    /// `None` disables the channel — both for banks persisted before the
    /// channel existed (serde default) and for rooms where the empty/occupied
    /// means don't separate at train time.
    #[serde(default)]
    pub mean_dist_threshold: Option<f32>,
}

impl PresenceSpecialist {
    /// Fit from anchors: variance threshold at the midpoint between the empty
    /// variance and the mean occupied variance; mean-shift threshold at half
    /// the empty→occupied mean distance (inert when the means don't separate).
    ///
    /// The variance channel is itself inert (never fires) when `occ_var`
    /// does not genuinely exceed `empty_var` (issue #1440): a midpoint
    /// threshold assumes occupied windows are noisier than the empty-room
    /// baseline, but a still/quiet occupant can measure *less* variance
    /// than an empty room's ambient/interference noise floor. Left
    /// unguarded, the midpoint then sits *below* the empty-room baseline
    /// itself, so a genuinely empty room reads "present" on every frame —
    /// worse than no signal at all. Matches the mean-shift channel, which
    /// already goes inert (`None`) under the equivalent condition.
    pub fn train(anchors: &[AnchorFeature]) -> Option<Self> {
        let empty = anchors.iter().find(|a| a.label == AnchorLabel::Empty)?;
        let occ: Vec<&Features> = anchors
            .iter()
            .filter(|a| a.label.expects_presence())
            .map(|a| &a.features)
            .collect();
        if occ.is_empty() {
            return None;
        }
        let occ_var = occ.iter().map(|f| f.variance).sum::<f32>() / occ.len() as f32;
        let occ_mean = occ.iter().map(|f| f.mean).sum::<f32>() / occ.len() as f32;
        let empty_var = empty.features.variance;
        let empty_mean = empty.features.mean;

        let mean_dist = (occ_mean - empty_mean).abs();
        let mean_dist_threshold = (mean_dist > 1e-4).then(|| 0.5 * mean_dist);

        let variance_separates = occ_var > empty_var * (1.0 + VARIANCE_SEPARATION_MARGIN);
        let threshold = if variance_separates {
            0.5 * (empty_var + occ_var)
        } else {
            f32::INFINITY
        };

        Some(Self {
            threshold,
            occupied_var: occ_var.max(empty_var + 1e-3),
            empty_mean,
            mean_dist_threshold,
        })
    }
}

impl Specialist for PresenceSpecialist {
    fn kind(&self) -> SpecialistKind {
        SpecialistKind::Presence
    }
    fn infer(&self, f: &Features) -> Option<SpecialistReading> {
        let by_variance = f.variance > self.threshold;
        let mean_dist = (f.mean - self.empty_mean).abs();
        let by_mean = self.mean_dist_threshold.is_some_and(|thr| mean_dist > thr);
        let present = by_variance || by_mean;

        // Confidence: strongest margin among the channels that are enabled.
        // An infinite threshold means the variance channel was disabled at
        // train time (issue #1440) — it must contribute 0, not the spurious
        // 1.0 that `(x - inf).abs() / span` would otherwise clamp to.
        let var_conf = if self.threshold.is_finite() {
            let var_span = (self.occupied_var - self.threshold).max(1e-3);
            ((f.variance - self.threshold).abs() / var_span).clamp(0.0, 1.0)
        } else {
            0.0
        };
        let mean_conf = self
            .mean_dist_threshold
            .map(|thr| ((mean_dist - thr).abs() / thr.max(1e-3)).clamp(0.0, 1.0))
            .unwrap_or(0.0);
        let confidence = var_conf.max(mean_conf);

        Some(SpecialistReading {
            kind: SpecialistKind::Presence,
            value: if present { 1.0 } else { 0.0 },
            confidence,
            label: Some(if present { "present" } else { "absent" }.into()),
        })
    }
}

