"""Offline review boundary and prospective command strings of the shared UI."""
import copy
import unittest
from unittest.mock import patch

from revisar_devrep_r5_n01 import CONNECTION_ID, check_guidance, main, review
from rx02_devrep_r4_n01.contract import runtime_plan


class ReviewTests(unittest.TestCase):
    def test_review_and_projection_never_access_devices_or_player(self):
        with (patch('serial.Serial', side_effect=AssertionError('No UART')),
              patch('preflight_devrep_r4.metadata_snapshot', side_effect=AssertionError('No USB')),
              patch('subprocess.run', side_effect=AssertionError('No audio player'))):
            report = review()
            plan = copy.deepcopy(report['plan'])
            evidence = check_guidance(plan)
        self.assertEqual(plan, report['plan'])
        self.assertTrue(evidence['simulation_only'] and evidence['sequence_verified'])
        self.assertFalse(evidence['capture_started'] or evidence['experimental_labels_created'])
        self.assertFalse(report['authorization_granted'] or report['physical_entrypoint_enabled'])
        self.assertEqual(report['declarations'], [f'declare {CONNECTION_ID}-{c} yes' for c in ('E', 'S')])
        self.assertEqual(report['acquisition_visualization_evidence']['rows'], 1192)
        self.assertFalse(report['acquisition_visualization_evidence']['quality_ok'])

    def test_proposed_identity_cannot_be_executed_as_consumed_R4(self):
        report = review()
        self.assertEqual(report['partition_group'], CONNECTION_ID)
        with self.assertRaises(ValueError):
            runtime_plan(report['plan'])
        with self.assertRaises(SystemExit) as stopped:
            main(['--execute-after-approval'])
        self.assertEqual(stopped.exception.code, 2)

    def test_return_and_last_declaration_wait_for_their_actual_ui_gates(self):
        evidence = check_guidance(review()['plan'])
        states = {stage['stage']: stage['rendered_text'] for stage in evidence['transcript']}
        self.assertNotIn('REGRESA', states['E_antes_de_confirmar_tono_final'])
        self.assertIn('REGRESA Y ESCRIBE LA DECLARACIÓN', states['regresar_y_declarar_E'])
        self.assertIn(f'declare {CONNECTION_ID}-E yes', states['regresar_y_declarar_E'])
        self.assertIn('80 s', states['regresar_y_declarar_E'])
        for stage in ('S_sin_prueba_de_cierre', 'S_sin_reproduccion_final'):
            self.assertNotIn(f'declare {CONNECTION_ID}-S yes', states[stage])
        self.assertIn(f'declare {CONNECTION_ID}-S yes', states['declarar_S_tras_cierre_simulado'])
        self.assertIn('80 s', states['declarar_S_tras_cierre_simulado'])
        patterns = evidence['waveform_patterns']
        self.assertEqual([p['specification'][0] for p in patterns], [2, 1, 2, 1, 3])
