"""Reuse the original offline helpers without their historical auto-initializer."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def chart_module():
    original=(ROOT/'src/offline_view.mjs').read_text()
    autorun="if(typeof document!=='undefined'){initialize(JSON.parse(document.getElementById('csi-data').textContent));}"
    if autorun not in original:raise ValueError('Original renderer initialization changed; review required')
    return original.replace(autorun,'// Historical auto-initialization omitted.')+'\n'+(ROOT/'src/csi_charts.mjs').read_text()
