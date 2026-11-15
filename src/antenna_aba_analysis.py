"""Offline A1-B-A2 consolidation; no acquisition, interpolation or causal verdict."""
import collections
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from capture_csi_multi import FIELDS, RECEIVERS
from continuity_diagnostics import analyze_continuity, distribution, intervals
from presence_v4_journal import digest

PHASES = ('A1', 'B', 'A2')
SCHEMA = 'continuity-antenna-aba-comparison-1'


def quantile(values, p):
    if not values or not 0 < p <= 1:
        raise ValueError('Nonempty observations and quantile in (0,1] required')
    return sorted(values)[math.ceil(p*len(values))-1]


def rssi_description(values):
    return dict(distribution(values), p10=quantile(values,.1), p90=quantile(values,.9),
                unit='dBm', histogram=dict(sorted(collections.Counter(str(x) for x in values).items())),
                population='Strict complete valid rows only; unequal sample counts, no missing-value filling')


def contrasts(values):
    return dict(A1=values['A1'], B=values['B'], A2=values['A2'],
        B_minus_A1=values['B']-values['A1'], A2_minus_A1=values['A2']-values['A1'],
        A2_minus_B=values['A2']-values['B'],
        B_minus_mean_of_A1_A2=values['B']-(values['A1']+values['A2'])/2,
        interpretation='Descriptive contrasts only; neither causal effects nor uncertainty estimates')


def close_verified(report):
    return (report['both_ports_closed_confirmed'] and all(
        item['confirmed'] and item['error'] is None and item['details']['open_attempts']==1 and
        item['details']['close_attempts']==1 and item['details']['is_open'] is False and
        item['details']['fd'] is None for item in report['closure'].values()))


def build_series(bundles):
    if set(bundles) != set(PHASES) or len({Path(x).resolve() for x in bundles.values()}) != 3:
        raise ValueError('Three distinct bundles keyed A1/B/A2 required')
    summary = dict(schema=SCHEMA, analysis_activity=dict(physical_UART_opened=False),
        quality_approval=False, causal_orientation_effect_established=False,
        permitted_uses=dict(eligible_windows=False,presence_labels=False,calibration=False,training=False,production=False),
        method=dict(interval='Original common 60s, return timestamps in [start,deadline)',
            gaps='Adjacent full valid rows only; edges reported separately; local clocks independent per RX',
            quantiles='Nearest rank ceil(p*n); conventional median; no interpolation',
            RSSI='Observed valid-row population; no estimate for unobserved receptions',
            control='RX-02 descriptive concurrent control; not randomized or replicated'),
        phases={}, contrasts={}, timeline={})
    plot_data={}; common_plan=None; sources=None; last_stop=None
    for phase in PHASES:
        bundle=Path(bundles[phase]); forensic=analyze_continuity(bundle)
        report=json.loads((bundle/'report.json').read_text())
        plan=json.loads((bundle/'plan.json').read_text()); metadata=json.loads((bundle/'metadata.json').read_text())
        expected='CONT-ANT-ABA-R3-'+phase
        if (report['diagnostic_id']!=expected or report['evidence_type']!='physical_capture' or
                report['fatal'] is not None or not report['completed_nominal_duration'] or not close_verified(report)):
            raise ValueError('Incomplete/failed/wrong physical phase: '+phase)
        if forensic['authorization'] != dict(reference=expected+'-UNICO',consumed=True,
                evidence_type='physical_capture',reattempt_permitted=False):
            raise ValueError('Wrong or unconsumed authorization: '+phase)
        frozen={k:v for k,v in plan.items() if k not in ('diagnostic_id','declarations')}
        if common_plan is None: common_plan=frozen
        if frozen!=common_plan: raise ValueError('Acquisition policy differs across phases')
        if sources is None: sources=metadata['sources']
        if metadata['sources']!=sources or not all(forensic['acquisition_sources_match_current'].values()):
            raise ValueError('Acquisition source hashes differ')
        start=forensic['interval']['common_start_ns']; stop=forensic['interval']['actual_stop_ns']
        if last_stop is not None and start <= last_stop:
            raise ValueError('Overlapping or unordered phases')
        wall=report['dual_observation']['start']['realtime_ns']
        summary['timeline'][phase]=dict(common_start_monotonic_ns=start,actual_stop_monotonic_ns=stop,
            common_start_utc=datetime.fromtimestamp(wall//1_000_000_000,timezone.utc).isoformat(),
            common_start_realtime_ns=wall,
            gap_from_previous_actual_stop_ns=None if last_stop is None else start-last_stop)
        last_stop=stop
        item=dict(diagnostic_id=expected,bundle_path=str(bundle),input_files=forensic['input_files'],
            integrity_ok=True,replay_ok=True,fatal=None,completed_nominal_duration=True,
            closure=report['closure'],both_ports_closed_confirmed=True,
            authorization=forensic['authorization'],quality_approval=False,
            interval=forensic['interval'],host_clocks=forensic['host_clocks'],storage=forensic['storage'],
            declarations=plan['declarations'],identities=metadata['identities'],
            acquisition_commit=metadata['git_commit'],acquisition_working_tree_status=metadata['working_tree_status'],
            acquisition_sources=metadata['sources'],source_hashes_match_current=True,receivers={},incidents=[])
        plot_data[phase]={}
        for rx,s in forensic['receivers'].items():
            raw=(bundle/(rx.lower()+'.serial.log')).read_bytes()
            points=[]
            for row in s['row_evidence']:
                literal=next(csv.reader([raw[row['byte_offset']:row['byte_end']].decode().strip()]))
                point={k:row[k] for k in ('line_1based','byte_offset','byte_end','line_sha256','ledger_seq','id','local_timestamp','queue_drops')}
                point.update(host_relative_ns=int(row['returned_ns'])-start,
                    rssi=int(literal[FIELDS.index('rssi')]))
                points.append(point)
            if not points: raise ValueError('No valid observations in phase: '+phase+' '+rx)
            value={k:v for k,v in s.items() if k not in ('row_evidence','nonrow_evidence','callback_transitions')}
            value['cadence_rows_per_second']=len(points)/60
            value['rssi']=rssi_description([p['rssi'] for p in points])
            value['continuity_flags']={key:sum(bool(t[key]) for t in s['callback_transitions'])
                for key in ('callback_restart','callback_gap','local_discontinuity','queue_drops_changed')}
            first=s['row_evidence'][0]['line_1based']
            value['anomalies_after_first_valid_row']=[l for l in s['nonrow_evidence']
                if l['line_1based']>=first and l['kind'] in ('invalid','reset','error')]
            item['receivers'][rx]=value
            plot_data[phase][rx]=dict(points=points,
                host_gaps_ms=[x/1e6 for x in intervals([p['host_relative_ns'] for p in points])],
                local_gaps_ms=[((b['local_timestamp']-a['local_timestamp'])%2**32)/1000
                               for a,b in zip(points,points[1:])])
        for incident in forensic['incidents']:
            item['incidents'].append({k:v for k,v in incident.items() if k!='context'})
        summary['phases'][phase]=item
    for rx in RECEIVERS:
        metrics={}
        for name,extract in (
            ('rows',lambda x:x['valid_complete_rows_common']),
            ('cadence_rows_per_second',lambda x:x['cadence_rows_per_second']),
            ('host_mean_gap_ns',lambda x:x['host_row_gaps_ns']['mean']),
            ('local_mean_gap_ns',lambda x:x['local_row_gaps_ns']['mean']),
            ('RSSI_mean_dBm',lambda x:x['rssi']['mean']),
            ('RSSI_median_dBm',lambda x:x['rssi']['median'])):
            metrics[name]=contrasts({p:extract(summary['phases'][p]['receivers'][rx]) for p in PHASES})
        summary['contrasts'][rx]=metrics
    summary['RX01_to_RX02_count_ratios']={p:summary['phases'][p]['receivers']['RX-01']['valid_complete_rows_common']/
        summary['phases'][p]['receivers']['RX-02']['valid_complete_rows_common'] for p in PHASES}
    summary['A2_did_not_reproduce_A1']=(summary['contrasts']['RX-01']['rows']['A2_minus_A1']!=0 or
        summary['contrasts']['RX-01']['RSSI_mean_dBm']['A2_minus_A1']!=0)
    summary['A2_reproduction_evidence']=dict(
        RX01_rows=summary['contrasts']['RX-01']['rows'],
        RX01_RSSI_mean=summary['contrasts']['RX-01']['RSSI_mean_dBm'],
        RX02_RSSI_mean=summary['contrasts']['RX-02']['RSSI_mean_dBm'],
        interpretation='Exact observed count/mean differences, not a statistical equivalence test. Mechanical return is declared; no orientation causality established')
    return summary,plot_data


def render_plots(summary, data, folder):
    """Pinned local Matplotlib, common axes; original points are never resampled."""
    import sys
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'.tools/comparacion-v3-python-v2'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy
    if matplotlib.__version__!='3.10.8' or numpy.__version__!='2.4.2':
        raise ValueError('Pinned existing Matplotlib/NumPy runtime required')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
                         'svg.hashsalt':'continuity-antenna-aba-1'})
    if any(max(data[p][rx][metric],default=0)>1500 for p in PHASES for rx in RECEIVERS
           for metric in ('host_gaps_ms','local_gaps_ms','read_return_gaps_ms')):
        raise ValueError('Observations exceed common gap plot axes; revise all axes together')
    if any(max(data[p][rx]['service_gaps_ms'],default=0)>50 for p in PHASES for rx in RECEIVERS):
        raise ValueError('Observations exceed common service axes')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    colors={'A1':'#1764ab','B':'#c7520a','A2':'#218350'}
    labels={'A1':'A1: apoyada','B':'B: 90° declarados','A2':'A2: regreso declarado'}
    figures=[];rxs=list(RECEIVERS)
    footer='Diagnóstico descriptivo. A2 no reproduce A1; sin causalidad por orientación ni aprobación de calidad.'
    def ecdf(ax,values,phase):
        x=sorted(values)
        ax.step(x,[i/len(x) for i in range(1,len(x)+1)],where='post',color=colors[phase],label=labels[phase])
    def save(fig,name,expected_limits):
        rendered=[]
        for ax,(xlim,ylim) in zip(fig.axes,expected_limits):
            ax.set_xlim(xlim);ax.set_ylim(ylim);ax.grid(alpha=.25)
            if list(ax.get_xlim())!=list(xlim) or list(ax.get_ylim())!=list(ylim):raise ValueError('Axes mismatch')
            rendered.append(dict(panel=ax.get_title(),xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim())))
        fig.text(.5,.014,footer,ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.045,1,.95))
        for ext in ('svg','png'):
            p=folder/(name+'.'+ext)
            fig.savefig(p,dpi=140,metadata={'Date':None} if ext=='svg' else {'Software':'Matplotlib 3.10.8'})
            if ext=='svg':p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
            figures.append(dict(path=p.name,sha256=digest(p),bytes=p.stat().st_size,axes=rendered))
        plt.close(fig)
    fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True,sharey=True)
    fig.suptitle('Filas válidas en intervalos comunes de 10 s')
    for ax,rx in zip(axs,rxs):
        for index,p in enumerate(PHASES):
            s=summary['phases'][p]['receivers'][rx]
            ax.bar([5+10*i+(index-1)*2 for i in range(6)],s['valid_rows_per_10s'],width=1.8,
                   label=labels[p]+f" (n={s['valid_complete_rows_common']})",color=colors[p])
        ax.set_title(rx);ax.set_ylabel('Filas / 10 s');ax.legend(loc='lower left',ncol=3,fontsize=9)
    axs[-1].set_xlabel('Tiempo desde inicio común de cada sesión (s)')
    save(fig,'cadencia',[([0,60],[0,55])]*2)
    for time_plot,name,title in ((False,'huecos_ecdf','Distribución empírica de huecos entre filas completas'),
                                 (True,'huecos_tiempo','Huecos host/local durante los 60 s completos')):
        fig,axs=plt.subplots(2,2,figsize=(12,7),sharex=True,sharey=True);fig.suptitle(title)
        for row,rx in enumerate(rxs):
            for col,key in enumerate(('host_gaps_ms','local_gaps_ms')):
                ax=axs[row,col]
                for p in PHASES:
                    v=data[p][rx][key]
                    if time_plot:
                        ax.scatter([q['host_relative_ns']/1e9 for q in data[p][rx]['points'][1:]],v,
                            s=11,alpha=.65,color=colors[p],label=labels[p])
                    else:ecdf(ax,v,p)
                if time_plot:ax.axhline(1000,color='#555555',linestyle='--',linewidth=.8)
                else:ax.axvline(1000,color='#555555',linestyle='--',linewidth=.8)
                ax.set_title(rx+' / '+('retorno host' if col==0 else 'reloj local'))
                ax.set_xlabel('Tiempo común (s)' if time_plot else 'Hueco (ms)')
                ax.set_ylabel('Hueco (ms)' if time_plot else 'Fracción acumulada');ax.legend(fontsize=8)
        save(fig,name,[([0,60],[0,1500]) if time_plot else ([0,1500],[0,1.02])]*4)
    fig,axs=plt.subplots(2,2,figsize=(12,7));fig.suptitle('RSSI condicionado a filas completas válidas')
    all_rssi=[v['rssi'] for p in PHASES for rx in rxs for v in data[p][rx]['points']]
    rssi_range=[min(all_rssi)-2,max(all_rssi)+2]
    limits=[]
    for row,rx in enumerate(rxs):
        for p in PHASES:
            points=data[p][rx]['points'];values=[x['rssi'] for x in points]
            axs[row,0].scatter([x['host_relative_ns']/1e9 for x in points],values,
                color=colors[p],s=10,alpha=.55,label=labels[p]+f' (n={len(values)})')
            ecdf(axs[row,1],values,p)
        axs[row,0].set_title(rx+' / evolución RSSI');axs[row,0].set_xlabel('Tiempo común (s)');axs[row,0].set_ylabel('RSSI (dBm)')
        axs[row,1].set_title(rx+' / distribución RSSI');axs[row,1].set_xlabel('RSSI (dBm)');axs[row,1].set_ylabel('Fracción acumulada')
        for ax in axs[row]:ax.legend(fontsize=8)
        limits.extend([([0,60],rssi_range),(rssi_range,[0,1.02])])
    save(fig,'rssi',limits)
    fig,axs=plt.subplots(2,3,figsize=(15,7));fig.suptitle('Servicio, retornos de bytes y latencias del host')
    limits=[]
    metrics=('return_to_persistence_start_ns','raw_persistence_ns','processing_after_raw_persistence_ns')
    metric_labels=('Espera','Write/flush/fsync','Procesamiento')
    for row,rx in enumerate(rxs):
        for p in PHASES:
            s=summary['phases'][p]['receivers'][rx]
            # Empirical samples recovered from the original read-only ledger.
            trace=data[p][rx]
            ecdf(axs[row,0],trace['service_gaps_ms'],p)
            ecdf(axs[row,1],trace['read_return_gaps_ms'],p)
        for index,p in enumerate(PHASES):
            s=summary['phases'][p]['receivers'][rx]
            axs[row,2].bar([i+(index-1)*.24 for i in range(3)],
                [s['timing'][m]['p99']/1e6 for m in metrics],width=.22,color=colors[p],label=labels[p])
        axs[row,0].set_title(rx+' / servicio');axs[row,0].set_xlabel('Intervalo (ms)');axs[row,0].set_ylabel('Fracción acumulada')
        axs[row,1].set_title(rx+' / retornos con bytes');axs[row,1].set_xlabel('Intervalo (ms)');axs[row,1].set_ylabel('Fracción acumulada')
        axs[row,2].set_title(rx+' / p99 por bloque');axs[row,2].set_ylabel('Latencia (ms)')
        axs[row,2].set_xticks(range(3),metric_labels)
        for ax in axs[row]:ax.legend(fontsize=8)
        limits.extend([([0,50],[0,1.02]),([0,1500],[0,1.02]),([-.6,2.6],[0,10])])
    save(fig,'transporte',limits)
    return dict(schema='continuity-antenna-aba-figures-1',runtime=dict(matplotlib=matplotlib.__version__,numpy=numpy.__version__),
                requirements_sha256=digest(root/'requirements-comparacion.txt'),files=figures,
                interpolation_of_observations=False,quality_approval=False)


def add_transport_samples(bundles, summary, plot_data):
    """Retain unbinned service/read samples for ECDFs; boundaries are explicit."""
    from continuity_diagnostics import service_gaps
    for phase in PHASES:
        events=[json.loads(l) for l in (Path(bundles[phase])/'ledger.jsonl').read_text().splitlines()]
        start=summary['phases'][phase]['interval']['common_start_ns']
        end=summary['phases'][phase]['interval']['common_deadline_ns']
        for rx in RECEIVERS:
            plot_data[phase][rx]['service_gaps_ms']=[v/1e6 for v in service_gaps(events,rx,start,end)]
            returns=[e['returned']['monotonic_ns'] for e in events if e['kind']=='read' and e['receiver']==rx and
                     start<=e['returned']['monotonic_ns']<end]
            plot_data[phase][rx]['read_return_gaps_ms']=[v/1e6 for v in intervals(returns)]
