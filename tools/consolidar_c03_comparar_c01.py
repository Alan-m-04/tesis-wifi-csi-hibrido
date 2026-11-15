#!/usr/bin/env python3
"""Audit only C03/C01 and describe existing E/S windows; no capture or model selection."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
import consolidar_rx02_c01 as c01
from comparar_fisicas_v3 import describe_block,stats
from rx02_c03.checkpoint import audit_c03_checkpoints
from presence_rx02_journal import audit_rx02
from campana_rx02_checkpoint import condition_hash

require,load,sha,inventory,write_new=c01.require,c01.load,c01.sha,c01.inventory,c01.write_new
RX='RX-02'
C01=ROOT/'results/local/piloto-rx02-r1-C01'
C02=ROOT/'results/local/piloto-rx02-r1-C02'
C03=ROOT/'results/local/piloto-rx02-r1-C03-checkpoint-r1'
PREPARATION=ROOT/'results/local/preparacion-C03-checkpoint-r1'
SOURCE_COMMIT='6161de0e4637f991eee542046124f62936a84e7e'


def describe_windows(root,audit):
    """Use every original prospectively included reference, with fixed LLTF52 definition."""
    root=Path(root);state=audit['state'];raw=(root/'rx-02.serial.log').read_bytes()
    events=load(root/'events.json');profile=load(ROOT/'config/csi_esp32s3.json')['firmware_ltf_config']
    processed={e['evidence']['line_1based']:e['now_ns'] for e in events if e['kind']=='line'}
    windows,data,traces={},{},{};membership=set()
    for w,conservative in zip(state['windows'],state['exploration']['windows']):
        refs=w['receivers'][RX]['included_line_references']
        require(conservative['receivers'][RX]['included_line_references']==refs,'Conservative membership differs')
        require(not membership.intersection(r['line_1based'] for r in refs),'Window membership overlaps')
        membership.update(r['line_1based'] for r in refs)
        require(all(processed[r['line_1based']]<w['T1_ns'] for r in refs),'Late processed row cannot be selected')
        coverage=c01.coverage_from_refs(refs,w['T0_ns'],w['T1_ns'])
        original=w['receivers'][RX]['coverage']
        require(all(original[k]==coverage[k] for k in ('included_rows','bins_5s','gaps_ns','max_gap_ns')),'Coverage reproduction differs')
        frames,means,reasons=[],[],[]
        for reference in refs:
            frame,mean,reason=c01.frame_from_reference(raw,reference,profile)
            frames.append(frame);means.append(mean);reasons.append(reason)
        description,independent_means=describe_block(frames,'LLTF')
        require(means==independent_means,'LLTF52 full-mask means disagree')
        if any(reasons):
            description['frame_mean_amplitude']=dict(n=0,mean=None,std_population=None,median=None,min=None,max=None,reason='required_row_or_tone_incomplete')
            description['mean_per_tone_temporal_std']=None
        rssi=[int(frame['original_fields']['rssi']) for frame in frames]
        metadata={key:dict(sorted(Counter(frame['original_fields'][key] for frame in frames).items())) for key in
            ('mac','channel','bandwidth','sig_mode','mcs','stbc','secondary_channel','rx_state','first_word_invalid','len','queue_drops','noise_floor','ant')}
        condition=w['condition']
        windows[condition]=dict(slot_id=w['id'],last=w['last'],T0_ns=str(w['T0_ns']),T1_ns=str(w['T1_ns']),
            requested_ns=str(w['requested_ns']),label=w['label'],coverage=coverage,
            label_after_T1_ns=w['label']['declaration_ns']-w['T1_ns'],
            window_quality_ok=w['window_quality_ok'],pilot_coverage_ok=w['pilot_coverage_ok'],label_quality_ok=w['label_quality_ok'],
            original_strict_eligible=w['eligible'],exploratory=next(item for item in audit['exploratory_eligibility']['windows'] if item['slot_id']==w['id']),
            rssi_dBm=stats(rssi),LLTF52=description,metadata=metadata,included_line_references=refs,
            mask_status='complete' if not any(reasons) else 'incomplete',mask_reasons=sorted({reason for reason in reasons if reason}))
        data[condition]=dict(time_s=[(int(ref['returned_ns'])-w['T0_ns'])/1e9 for ref in refs],rssi_dBm=rssi,mean_amplitude=means)
        traces[condition]=frames
    require(set(windows)=={'E','S'},'Exactly original E and S required')
    return windows,data,traces


def consolidate_c03(root=C03,preparation=PREPARATION):
    root=Path(root);preparation=Path(preparation);before=inventory(root)
    audit=audit_c03_checkpoints(root);state=audit['state']
    require(state['connection_id']=='RX02-C03' and state['evidence_type']=='physical_capture','Existing physical C03 only')
    require([(w['id'],w['condition'],w['last']) for w in state['windows']]==[('RX02-C03-E','E',False),('RX02-C03-S','S',True)],'C03 order/last changed')
    plan,provenance=load(root/'plan.json'),load(root/'provenance.json')
    require(state['partition_group']=='RX02-C03' and state['future_partition']=='development_future','Original whole-connection partition required')
    for source in provenance['sources']:
        original=subprocess.check_output(['git','show',SOURCE_COMMIT+':'+source['path']],cwd=ROOT)
        import hashlib
        require(hashlib.sha256(original).hexdigest()==source['sha256'],'C03 source differs from published implementation')
    auth=load(preparation/'autorizacion-unica.json');preflight=load(preparation/'preflight.json');history=load(preparation/'historia-conexiones-confirmada.json')
    require(auth['authorization_granted'] is True and auth['max_attempts']==1 and auth['retry_allowed'] is False,'New single authorization required')
    require(auth['plan_sha256']==sha(root/'plan.json')==sha(preparation/'plan-autorizado.json'),'Captured/authorized plan mismatch')
    require(auth['reference']==provenance['transport']['authorization_reference']=='RX02-C03-CHECKPOINT-R1:'+sha(root/'plan.json'),'C03 authorization reference differs')
    require(auth['preflight_sha256']==sha(preparation/'preflight.json') and auth['history_sha256']==sha(preparation/'historia-conexiones-confirmada.json'),'Support reference differs')
    require(preflight['identities']==provenance['transport']['identities'] and preflight['physical_UART_opened'] is False,'Preflight identity evidence differs')
    require(preflight['conditions_sha256']==condition_hash(plan),'Preflight conditions differ')
    windows,data,traces=describe_windows(root,audit)
    events=load(root/'events.json');lines=[e['evidence'] for e in events if e['kind']=='line'];rows=[line for line in lines if line['kind']=='row']
    raw=(root/'rx-02.serial.log').read_bytes()
    for reference in rows:c01.verify_reference(raw,reference)
    operations=[json.loads(line) for line in (root/'operations.jsonl').read_text().splitlines()]
    counts=Counter(op['op'] for op in operations)
    opened=next(op['now_ns'] for op in operations if op['op']=='opened');closing=next(op['now_ns'] for op in operations if op['op']=='closing')
    supporting=[preparation/name for name in ('autorizacion-unica.json','plan-autorizado.json','plan-revisado-sin-autorizacion.json','preflight.json','condiciones-actuales.json','historia-conexiones-confirmada.json')]
    in_windows=sum(w['coverage']['included_rows'] for w in windows.values())
    summary=dict(schema='tesis-rx02-c03-descriptive-1',acquisition_source_commit=SOURCE_COMMIT,bundle_path=str(root.relative_to(ROOT)),
        original_files=before,supporting_files={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in supporting},
        audit=dict(integrity_ok=audit['integrity_ok'],replay_ok=audit['replay_ok'],operations=audit['operations'],physical_UART_opened_by_audit=False,
            persistence_revision=audit['persistence_revision'],integration_revision=audit['integration_revision'],exploratory_eligibility=audit['exploratory_eligibility']),
        connection=dict(result=state['connection'],fatal=state['fatal'],line_kinds=dict(Counter(line['kind'] for line in lines)),
            total_CSI_rows=len(rows),in_windows=in_windows,outside_windows=len(rows)-in_windows,
            first_callback_id=rows[0]['id'],last_callback_id=rows[-1]['id'],callbacks_consecutive=all(b['id']==a['id']+1 for a,b in zip(rows,rows[1:])),
            queue_drops_values=sorted({row['queue_drops'] for row in rows}),operation_counts=dict(counts),
            open_to_close_s=(state['closed'][RX]['at_ns']-opened)/1e9,open_to_closing_s=(closing-opened)/1e9,
            journal_span_s=(operations[-1]['now_ns']-operations[0]['now_ns'])/1e9,initial_available_ns=str(state['initial_available_ns']),tails=state['tails']),
        windows=windows,provenance=provenance,captured_plan=plan,runtime=load(root/'summary.json')['runtime'],close_receipt=load(root/'close-receipt.json'),
        checkpoint_status=audit['persistence_status'],authorization_consumed=load(root/'authorization-consumed.json'),signals=state['signals'],
        supporting_declarations=dict(operator_authorization=auth,preflight=preflight,connection_history=history),
        partition=dict(group=state['partition_group'],future_partition=state['future_partition'],split_rows_or_windows=False),
        permitted_uses=dict(calibration=False,training=False,production=False))
    require(summary['checkpoint_status']['raw_syncs']==counts['chunk'],'Raw sync/read count differs')
    require(inventory(root)==before,'C03 originals changed')
    return summary,data,traces,audit


def comparison(a,b):
    fixed=('policy','receivers','ports','baud','storage_policy','transmitter','line_policy_revision','eligibility_revision')
    rows={}
    def difference(x,y):return None if x is None or y is None else x-y
    for condition in ('E','S'):
        x=a['windows'][condition];y=b['windows'][condition]
        rows[condition]=dict(C01=dict(rows=x['coverage']['included_rows'],rssi_dBm=x['rssi_dBm'],LLTF52=x['LLTF52'],mask_status=x['mask_status']),
            C03=dict(rows=y['coverage']['included_rows'],rssi_dBm=y['rssi_dBm'],LLTF52=y['LLTF52'],mask_status=y['mask_status']),
            C03_minus_C01=dict(rssi_mean_dB=difference(y['rssi_dBm']['mean'],x['rssi_dBm']['mean']),
                LLTF52_mean_amplitude=difference(y['LLTF52']['frame_mean_amplitude']['mean'],x['LLTF52']['frame_mean_amplitude']['mean']),
                LLTF52_frame_mean_temporal_std=difference(y['LLTF52']['frame_mean_amplitude']['std_population'],x['LLTF52']['frame_mean_amplitude']['std_population']),
                LLTF52_mean_per_tone_temporal_std=difference(y['LLTF52']['mean_per_tone_temporal_std'],x['LLTF52']['mean_per_tone_temporal_std'])))
    return dict(schema='tesis-rx02-C01-C03-comparison-1',conditions=rows,method=a['method'],
        fixed_plan_fields_equal={key:a['captured_plan'][key]==b['captured_plan'][key] for key in fixed},
        partition_groups=[a['partition'],b['partition']],
        persistence=dict(C01='historical raw and every operation fsync',C03=b['captured_plan']['persistence_revision']),
        mounting=dict(C01=a['captured_plan']['mounting_reference'],C03=b['captured_plan']['mounting_reference'],
            C01_environment=a['captured_plan']['environment'],C03_environment=b['captured_plan']['environment'],
            scope='Same positions/antennas declared, not remeasured geometry, AGC or RF equivalence'),
        unused_RX01=dict(C01=a['captured_plan']['unused_receiver'],C03=b['captured_plan']['unused_receiver']),
        scope='Only two development connections and predefined RSSI/LLTF52 descriptive definitions; no model/feature selection or reserve access',
        reserve_C04_C06_observations_opened=False,causal_presence_effect_established=False,
        permitted_uses=dict(calibration=False,training=False,production=False))


def render_plots(summaries,data,folder):
    sys.path.insert(0,str(ROOT/'.tools/comparacion-v3-python-v2'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy
    require(matplotlib.__version__=='3.10.8' and numpy.__version__=='2.4.2','Pinned plotting runtime required')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.fonttype':'none','svg.hashsalt':'C01-C03-descriptive-1'})
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    all_rssi=[v for sid in ('C01','C03') for cond in ('E','S') for v in data[sid][cond]['rssi_dBm']]
    all_amp=[v for sid in ('C01','C03') for cond in ('E','S') for v in data[sid][cond]['mean_amplitude'] if v is not None]
    tones=[tone for sid in ('C01','C03') for cond in ('E','S') for tone in summaries[sid]['windows'][cond]['LLTF52']['per_tone'] if tone['n']]
    low=min(tone['mean']-tone['std_population'] for tone in tones);high=max(tone['mean']+tone['std_population'] for tone in tones)
    axes=dict(time_s=[0,30],tones=[-32,31],rssi=[min(all_rssi)-1,max(all_rssi)+1],amplitude=[0,max(all_amp,default=1)*1.08],
        profile=[min(0,low*1.08),high*1.08],sigma=[0,max(t['std_population'] for t in tones)*1.08],gap_ms=[0,550])
    colors={'C01':'#1764ab','C03':'#c7520a'};artifacts=[]
    for name in ('rssi','amplitud_lltf52','perfil_lltf52','variabilidad_lltf52','cobertura'):
        fig,axs=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey=True)
        xlim=axes['tones'] if name in ('perfil_lltf52','variabilidad_lltf52') else axes['time_s']
        ylim=axes[{'rssi':'rssi','amplitud_lltf52':'amplitude','perfil_lltf52':'profile','variabilidad_lltf52':'sigma','cobertura':'gap_ms'}[name]]
        for row,cond in enumerate(('E','S')):
            for column,sid in enumerate(('C01','C03')):
                ax=axs[row,column];w=summaries[sid]['windows'][cond];d=data[sid][cond]
                if name in ('rssi','amplitud_lltf52'):
                    metric='rssi_dBm' if name=='rssi' else 'mean_amplitude'
                    pairs=[(t,v) for t,v in zip(d['time_s'],d[metric]) if v is not None]
                    ax.scatter([p[0] for p in pairs],[p[1] for p in pairs],s=10,color=colors[sid])
                    ax.set_ylabel('RSSI (dBm)' if name=='rssi' else 'Media LLTF52 (int8 sin calibrar)')
                elif name in ('perfil_lltf52','variabilidad_lltf52'):
                    support=[t for t in w['LLTF52']['per_tone'] if t['n']]
                    if name=='perfil_lltf52':
                        ax.errorbar([t['index'] for t in support],[t['mean'] for t in support],yerr=[t['std_population'] for t in support],fmt='o',ms=3,lw=.7,color=colors[sid])
                    else:ax.scatter([t['index'] for t in support],[t['std_population'] for t in support],s=12,color=colors[sid])
                    ax.set_ylabel('Media ± σ temporal por tono' if name=='perfil_lltf52' else 'σ temporal por tono')
                else:
                    gaps=[g/1e6 for g in w['coverage']['gaps_ns']];times=d['time_s']
                    ax.scatter([times[0],*times[1:],30],gaps,s=12,color=colors[sid])
                    ax.scatter([times[0],30],[gaps[0],gaps[-1]],marker='^',s=40,color=colors[sid])
                    ax.axhline(500,color='#555',linestyle='--',lw=.8)
                    ax.set_ylabel('Hueco host con bordes (ms)')
                ax.set_title(sid+' · '+('Vacío E' if cond=='E' else 'Sentado S')+' · n='+str(w['coverage']['included_rows']))
                ax.set_xlabel('Índice de subportadora' if name in ('perfil_lltf52','variabilidad_lltf52') else 'Tiempo relativo a T0 (s)')
                ax.set_xlim(xlim);ax.set_ylim(ylim);ax.grid(alpha=.25)
        fig.text(.5,.012,'Ventanas exploratorias · conexiones rechazadas por preámbulo · sin clasificación ni causalidad de presencia',ha='center',fontsize=8)
        fig.tight_layout(rect=(0,.035,1,1))
        drawn=[dict(title=ax.get_title(),xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim())) for ax in fig.axes]
        require(all(ax['xlim']==xlim and ax['ylim']==ylim for ax in drawn),'Common scales differ')
        for ext in ('svg','png'):
            path=folder/(name+'.'+ext)
            fig.savefig(path,dpi=150,metadata={'Date':None} if ext=='svg' else {'Software':'Matplotlib 3.10.8'})
            if ext=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
            artifacts.append(dict(path=str(path.relative_to(folder.parent)),bytes=path.stat().st_size,sha256=sha(path),axes=drawn))
        plt.close(fig)
    return dict(schema='tesis-C01-C03-figures-1',runtime=dict(matplotlib=matplotlib.__version__,numpy=numpy.__version__),common_axes=axes,figures=artifacts)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new',type=Path,required=True)
    args=parser.parse_args(argv);out=args.output_new.resolve()
    require(not out.exists() and not any(out.is_relative_to(p) or p.is_relative_to(out) for p in (C01,C02,C03,PREPARATION)), 'Exclusive new output outside all originals required')
    a,ad,at,aa=c01.consolidate(C01);b,bd,bt,ba=consolidate_c03()
    c02_before=inventory(C02);ca=audit_rx02(C02)
    require(ca['state']['fatal']=='availability_gap:RX-02' and ca['state']['tails'][RX]['bytes']==349,'C02 historical rejection/tail changed')
    summary=dict(schema='tesis-C03-and-C01-description-1',C01=a,C03=b,comparison=comparison(a,b),
        C02_preserved=dict(integrity_ok=ca['integrity_ok'],replay_ok=ca['replay_ok'],fatal=ca['state']['fatal'],tails=ca['state']['tails'],
            partition_group=ca['state']['partition_group'],future_partition=ca['state']['future_partition'],
            windows=[dict(id=w['id'],label=w['label']) for w in ca['state']['windows']],files=c02_before),
        physical_UART_opened_by_analysis=False,reserve_C04_C06_observations_opened=False)
    out.mkdir(parents=True,exist_ok=False)
    for name,value in [('audit-C01.json',aa),('audit-C03.json',ba),('audit-C02-preserved.json',ca),
        ('observations.local.json',{'C01':ad,'C03':bd}),('traces.local.json',{'C01':at,'C03':bt})]:write_new(out/name,value)
    figures=render_plots({'C01':a,'C03':b},{'C01':ad,'C03':bd},out/'figures')
    summary['analysis_sources']={name:sha(ROOT/name) for name in ('tools/consolidar_c03_comparar_c01.py','tools/consolidar_rx02_c01.py','tools/comparar_fisicas_v3.py','src/canonical_csi.py','src/csi_correspondence.py','src/presence_offline.py','requirements-comparacion.txt')}
    summary['figures']=figures
    for path,original in ((C01,a['original_files']),(C03,b['original_files']),(C02,c02_before)):
        require(inventory(path)==original,'Original changed while rendering')
    write_new(out/'summary.json',summary);write_new(out/'figures.json',figures);write_new(out/'files.json',inventory(out))
    print(json.dumps(dict(output=str(out),C03_rows=b['connection']['total_CSI_rows'],windows={c:{'rows':w['coverage']['included_rows'],'bins':w['coverage']['bins_5s'],'max_gap_ms':w['coverage']['max_gap_ns']/1e6,'rssi_mean':w['rssi_dBm']['mean'],'amplitude_mean':w['LLTF52']['frame_mean_amplitude']['mean'],'mean_per_tone_temporal_std':w['LLTF52']['mean_per_tone_temporal_std']} for c,w in b['windows'].items()},checkpoint_status=b['checkpoint_status'],reserve_C04_C06_observations_opened=False),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
