    pub fn expects_presence(&self) -> bool {
        !matches!(self, AnchorLabel::Empty)
    }
