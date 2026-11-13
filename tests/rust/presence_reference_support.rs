// Test scaffolding only. Original numeric bodies are inserted by the verifier.
// No serde, Cargo, sockets, serial APIs or physical samples.
#![allow(dead_code)]
use std::io::{self, BufRead};

#[derive(Clone, Copy, PartialEq)]
enum AnchorLabel { Empty, StandStill, Sit, LieDown, BreatheSlow, BreatheNormal, SmallMove, SleepPosture }
impl AnchorLabel {
// @@ORIGINAL_EXPECTS_PRESENCE@@
}
struct Features { mean: f32, variance: f32 }
struct AnchorFeature { label: AnchorLabel, features: Features }
enum SpecialistKind { Presence }
struct SpecialistReading { kind: SpecialistKind, value: f32, confidence: f32, label: Option<String> }
trait Specialist {
    fn kind(&self) -> SpecialistKind;
    fn infer(&self, f: &Features) -> Option<SpecialistReading>;
}

// @@ORIGINAL_PRESENCE@@

fn number<'a>(words: &mut impl Iterator<Item = &'a str>) -> f32 {
    f32::from_bits(u32::from_str_radix(words.next().unwrap(), 16).unwrap())
}
fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let mut words = line.split_whitespace();
        let id = words.next().unwrap();
        let n: usize = words.next().unwrap().parse().unwrap();
        let mut anchors = Vec::new();
        for _ in 0..n {
            let label = match words.next().unwrap() {
                "0" => AnchorLabel::Empty, "1" => AnchorLabel::StandStill,
                "2" => AnchorLabel::Sit, "3" => AnchorLabel::LieDown,
                "4" => AnchorLabel::BreatheSlow, "5" => AnchorLabel::BreatheNormal,
                "6" => AnchorLabel::SmallMove, "7" => AnchorLabel::SleepPosture,
                _ => panic!("Unknown synthetic label"),
            };
            anchors.push(AnchorFeature { label, features: Features { mean: number(&mut words), variance: number(&mut words) } });
        }
        let query = Features { mean: number(&mut words), variance: number(&mut words) };
        assert!(words.next().is_none());
        if let Some(model) = PresenceSpecialist::train(&anchors) {
            let reading = model.infer(&query).unwrap();
            let mean_thr = model.mean_dist_threshold.map(|v| format!("{:08x}", v.to_bits())).unwrap_or("NONE".into());
            println!("{} MODEL {:08x} {:08x} {:08x} {} {:08x} {:08x} {}", id,
                     model.threshold.to_bits(), model.occupied_var.to_bits(), model.empty_mean.to_bits(), mean_thr,
                     reading.value.to_bits(), reading.confidence.to_bits(), reading.label.unwrap());
        } else {
            println!("{} NONE", id);
        }
    }
}
