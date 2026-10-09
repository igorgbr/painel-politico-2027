import json
from pathlib import Path
import unittest
from backend.sources.senate_sessions import parse_evidence,exercises,reconcile,RECORTES

FIXTURES=Path(__file__).parent/'fixtures/senate-session-120'
TIME='2026-10-09T01:46:00Z'

class SenateSessionTests(unittest.TestCase):
    def setUp(self):
        self.text=(FIXTURES/'diario.txt').read_text()
        self.raw=(FIXTURES/'votes.json').read_bytes()
        self.types=(FIXTURES/'types.json').read_bytes()
        self.votes,self.present,self.meanings=parse_evidence(self.text,self.raw,self.types)
        self.ranges=exercises((FIXTURES/'mandates.json').read_bytes(),'6009')

    def history(self,code='6009',ranges=None,licenses=None):
        return reconcile(code,self.votes,self.present,self.meanings,self.ranges if ranges is None else ranges,licenses or [],TIME)

    def test_continuations_count_once_and_secret_vote_remains_private(self):
        h=self.history()
        self.assertEqual(h['totalSessoes'],1)
        self.assertEqual(h['participacoesConferidas'],1)
        self.assertEqual(len(h['sessoes'][0]['votacoes']),2)
        self.assertEqual(h['sessoes'][0]['votacoes'][0]['registro'],'Votou')
        self.assertIsNone(h['naoJustificada'])
        self.assertEqual(len(self.present),76)

    def test_secret_vote_description_never_propagates_an_individual_choice(self):
        raw=json.loads(self.raw)
        for row in raw[0]['votos']:
            if str(row['codigoParlamentar'])=='6009':row['descricaoVotoParlamentar']='Escolha individual: SIM'
        votes,present,meanings=parse_evidence(self.text,json.dumps(raw),self.types)
        h=reconcile('6009',votes,present,meanings,self.ranges,[],TIME)
        self.assertEqual(h['sessoes'][0]['votacoes'][0]['descricao'],'Votou')
        self.assertNotIn('Escolha individual',json.dumps(h))

    def test_one_registered_vote_does_not_prove_all_participation(self):
        h=self.history('6331')  # Sérgio Moro: Votou + P-NRV; DSF marca X/X.
        self.assertEqual(h['comparecimentosRegistrados'],1)
        self.assertEqual(h['participacoesConferidas'],0)
        self.assertEqual(h['pendentes'],1)
        self.assertIsNone(h['naoJustificada'])

    def test_activity_is_recorded_justification_not_unjustified_absence(self):
        h=self.history('285')
        self.assertEqual(h['comparecimentosRegistrados'],0)
        self.assertEqual(h['justificativasRegistradas'],1)
        self.assertIsNone(h['naoJustificada'])

    def test_communication_or_missing_vote_never_becomes_unjustified_absence(self):
        for sigla in ['AUS','NCom','NR','P-NRV','unknown']:
            for v in self.votes:
                if v['votacaoSecreta']=='S':continue
                for r in v['votos']:
                    if str(r['codigoParlamentar'])=='285':r['siglaVotoParlamentar']=sigla
            h=self.history('285')
            self.assertEqual(h['pendentes'],1)
            self.assertIsNone(h['naoJustificada'])

    def test_effective_license_covers_only_its_actual_dates(self):
        license=dict(id='1',inicio='2026-09-03',fim='2026-09-03',inicioPrevisto='2026-09-01',fimPrevisto='2026-09-03')
        h=self.history('6331',licenses=[{'licencas':[license],'fontes':['licencas']}])
        self.assertEqual(h['justificativasRegistradas'],1)
        for mutation in [dict(license,inicio=None,fim=None),dict(license,fim=None),dict(license,inicio='2026-09-01',fim='2026-09-01')]:
            h=self.history('6331',licenses=[{'licencas':[mutation],'fontes':['licencas']}])
            self.assertEqual(h['pendentes'],1)

    def test_exercise_changes_and_outside_exercise_are_not_absences(self):
        h=self.history('6342',ranges=[{'inicio':'2026-09-03','fim':'2031-01-31'}])
        self.assertEqual(h['participacoesConferidas'],1)
        self.assertEqual(h['sessoes'][0]['votacoes'][0]['classificacao'],'fora-exercicio')
        h=self.history('99999',ranges=[])
        self.assertEqual(h['foraExercicio'],1)
        self.assertEqual(h['pendentes'],0)
        self.assertIsNone(h['naoJustificada'])
        with self.assertRaises(ValueError):self.history(ranges=[])

    def test_diary_counts_unmatched_names_and_other_sessions_fail_closed(self):
        for text in [self.text.replace('Compareceram 76','Compareceram 75'),self.text.replace('120ª Sessão','121ª Sessão'),self.text.replace('Astr. Marcos Pontes','Nome Desconhecido')]:
            with self.assertRaises(ValueError):parse_evidence(text,self.raw,self.types)

    def test_duplicate_voting_wrong_identity_and_secret_choices_rejected(self):
        for mutation in ['duplicate','identity','secret','counts']:
            votes=json.loads(self.raw)
            if mutation=='duplicate':votes[1]=votes[0]
            if mutation=='identity':votes[1]['votos'][0]['siglaUFParlamentar']='SP'
            if mutation=='secret':votes[0]['votos'][0]['siglaVotoParlamentar']='Sim'
            if mutation=='counts':votes[0]['totalVotosSim']=62
            with self.assertRaises(ValueError):parse_evidence(self.text,json.dumps(votes),self.types)
        with self.assertRaises(ValueError):exercises((FIXTURES/'mandates.json').read_bytes(),'285')

class SenateExpandedSessionTests(unittest.TestCase):
    def setUp(self):
        self.raw=(FIXTURES.parent/'senate-votes-august.json').read_bytes()
        self.types=(FIXTURES/'types.json').read_bytes()
        self.ranges=exercises((FIXTURES/'mandates.json').read_bytes(),'6009')

    def evidence(self,number):
        cut=next(c for c in RECORTES if c['numero']==number)
        text=(FIXTURES.parent/f'senate-session-{number}'/'diario.txt').read_text()
        votes,present,meanings=parse_evidence(text,self.raw,self.types,cut)
        return cut,text,votes,present,meanings

    def test_no_nominal_confirms_presence_only_and_empty_api_is_rejected(self):
        cut,text,votes,present,meanings=self.evidence(111)
        self.assertEqual(len(present),80);self.assertEqual(votes,[])
        h=reconcile('6009',votes,present,meanings,self.ranges,[],TIME,cut)
        self.assertEqual(h['comparecimentosConferidos'],1)
        self.assertEqual(h['participacoesConferidas'],0)
        self.assertEqual(h['sessoes'][0]['classificacao'],'comparecimento-conferido')
        self.assertIsNone(h['naoJustificada'])
        with self.assertRaises(ValueError):parse_evidence(text,b'[]',self.types,cut)
        for code,ranges,status in [('99999',self.ranges,'pendente'),('6009',[],'error'),('99999',[],'fora-exercicio')]:
            if status=='error':
                with self.assertRaises(ValueError):reconcile(code,votes,present,meanings,ranges,[],TIME,cut)
            else:self.assertEqual(reconcile(code,votes,present,meanings,ranges,[],TIME,cut)['sessoes'][0]['classificacao'],status)

    def test_three_nominals_require_all_and_blank_diary_vote_preserves_presidency(self):
        cut,text,votes,present,meanings=self.evidence(113)
        self.assertEqual(len(present),80);self.assertEqual(len(votes),3)
        self.assertFalse(present['3830']['votoRegistrado'])
        h=reconcile('3830',votes,present,meanings,self.ranges,[],TIME,cut)
        self.assertEqual(h['participacoesConferidas'],1)  # Presidency in all three nominal votes.
        missing=next(code for code in present if any(str(r['codigoParlamentar'])==code and r['siglaVotoParlamentar']=='P-NRV' for v in votes for r in v['votos']))
        h=reconcile(missing,votes,present,meanings,self.ranges,[],TIME,cut)
        self.assertEqual(h['pendentes'],1);self.assertIsNone(h['naoJustificada'])
        for mutation in ['missing-vote','wrong-total','wrong-session']:
            data=json.loads(self.raw)
            if mutation=='missing-vote':data.pop()
            if mutation=='wrong-total':data[0]['votos'][0]['siglaVotoParlamentar']='Não'
            if mutation=='wrong-session':data[0]['numeroSessao']=111
            with self.assertRaises(ValueError):parse_evidence(text,json.dumps(data),self.types,cut)

    def test_single_vote_mark_cannot_be_misread_as_presence(self):
        cut,text,_,_,_=self.evidence(113)
        lines=text.splitlines();changed=False
        for i,line in enumerate(lines):
            if 'Carlos Portinho' in line and line.rstrip().endswith('X'):
                lines[i]=line.rstrip()[:-1]+' '*17+'X';changed=True;break
        self.assertTrue(changed)
        with self.assertRaises(ValueError):parse_evidence('\n'.join(lines),self.raw,self.types,cut)

    def test_compact_official_page_range_needs_correct_offset_and_printed_pages(self):
        cut,text,_,_,_=self.evidence(113)
        excerpt=text.lstrip('\f')
        self.assertEqual(len(parse_evidence(excerpt,self.raw,self.types,cut,100)[1]),80)
        with self.assertRaises(ValueError):parse_evidence(excerpt,self.raw,self.types,cut)
        with self.assertRaises(ValueError):parse_evidence(excerpt.replace('Compareceram 80','Compareceram 79'),self.raw,self.types,cut,100)


class SenateJulySessionTests(unittest.TestCase):
    def setUp(self):
        self.raw=(FIXTURES.parent/'senate-votes-july.json').read_bytes()
        self.types=(FIXTURES/'types.json').read_bytes()
        self.ranges=exercises((FIXTURES/'mandates.json').read_bytes(),'6009')

    def evidence(self,number):
        cut=next(c for c in RECORTES if c['numero']==number)
        text=(FIXTURES.parent/f'senate-session-{number}'/'diario.txt').read_text()
        votes,present,meanings=parse_evidence(text,self.raw,self.types,cut)
        return cut,text,votes,present,meanings

    def test_two_constitutional_rounds_are_distinct_votes_in_one_session(self):
        cut,_,votes,present,meanings=self.evidence(106)
        self.assertEqual(len(present),78)
        self.assertEqual([str(v['codigoSessaoVotacao']) for v in votes],['7096','7097'])
        h=reconcile('6009',votes,present,meanings,self.ranges,[],TIME,cut)
        self.assertEqual(h['totalSessoes'],1)
        self.assertEqual(h['participacoesConferidas'],1)
        abstained=next(str(r['codigoParlamentar']) for r in votes[0]['votos'] if r['siglaVotoParlamentar']=='Abstenção')
        self.assertEqual(reconcile(abstained,votes,present,meanings,self.ranges,[],TIME,cut)['participacoesConferidas'],1)
        self.assertIsNone(h['naoJustificada'])

    def test_participation_in_main_text_does_not_cover_later_amendments(self):
        cut,_,votes,present,meanings=self.evidence(107)
        self.assertEqual(len(present),76)
        self.assertEqual(len(votes),3)
        main_participants={str(r['codigoParlamentar']) for r in votes[0]['votos'] if r['siglaVotoParlamentar']=='Sim'}
        later_pending={str(r['codigoParlamentar']) for r in votes[-1]['votos'] if r['siglaVotoParlamentar']=='P-NRV'}
        code=next(iter(main_participants & later_pending & set(present)))
        h=reconcile(code,votes,present,meanings,self.ranges,[],TIME,cut)
        self.assertEqual(h['pendentes'],1)
        self.assertEqual(h['participacoesConferidas'],0)
        self.assertIsNone(h['naoJustificada'])

    def test_cross_session_or_missing_round_cannot_be_accepted(self):
        cut,text,_,_,_=self.evidence(106)
        for mutation in ['missing-round','wrong-result','wrong-session']:
            data=json.loads(self.raw)
            if mutation=='missing-round':data.pop(1)
            if mutation=='wrong-result':data[0]['votos'][0]['siglaVotoParlamentar']='Não'
            if mutation=='wrong-session':data[0]['numeroSessao']=107
            with self.assertRaises(ValueError):parse_evidence(text,json.dumps(data),self.types,cut)

    def test_three_non_nominal_sessions_confirm_only_their_own_presence(self):
        for number,count in [(98,80),(100,76),(102,68)]:
            with self.subTest(sessao=number):
                cut,_,votes,present,meanings=self.evidence(number)
                self.assertEqual(votes,[])
                self.assertEqual(len(present),count)
                h=reconcile('6009',votes,present,meanings,self.ranges,[],TIME,cut)
                self.assertEqual(h['comparecimentosConferidos'],1)
                self.assertEqual(h['participacoesConferidas'],0)
                self.assertIsNone(h['naoJustificada'])

    def test_neighboring_votes_do_not_prove_presence_in_a_non_nominal_session(self):
        cut,text,votes,present,meanings=self.evidence(102)
        self.assertNotIn('3830',present)  # Davi presided over the later session 106.
        h=reconcile('3830',votes,present,meanings,self.ranges,[],TIME,cut)
        self.assertEqual(h['pendentes'],1)
        self.assertEqual(h['comparecimentosConferidos'],0)
        self.assertEqual(h['justificativasRegistradas'],0)
        self.assertIsNone(h['naoJustificada'])
        with self.assertRaises(ValueError):parse_evidence(text,b'[]',self.types,cut)

    def test_extraordinary_session_requires_its_own_type_and_legislative_header(self):
        cut,text,votes,present,meanings=self.evidence(93)
        self.assertEqual(cut['tipo'],'DEX')
        self.assertEqual(len(present),71)
        self.assertEqual(votes,[])
        self.assertEqual(reconcile('6009',votes,present,meanings,self.ranges,[],TIME,cut)['comparecimentosConferidos'],1)
        for wrong in [dict(cut,tipo='DOR'),dict(cut,tipo='ESP')]:
            with self.assertRaises(ValueError):parse_evidence(text,self.raw,self.types,wrong)
        for wrong in [text.replace('93ª Sessão Deliberativa Extraordinária','93ª Sessão Deliberativa Ordinária'),text.replace('4ª Sessão Legislativa Ordinária','4ª Sessão Legislativa Extraordinária')]:
            with self.assertRaises(ValueError):parse_evidence(wrong,self.raw,self.types,cut)


class SenateJuneSessionTests(unittest.TestCase):
    def setUp(self):
        self.raw=(FIXTURES.parent/'senate-votes-june.json').read_bytes()
        self.types=(FIXTURES/'types.json').read_bytes()
        self.ranges=exercises((FIXTURES/'mandates.json').read_bytes(),'6009')

    def evidence(self,number):
        cut=next(c for c in RECORTES if c['numero']==number)
        text=(FIXTURES.parent/f'senate-session-{number}'/'diario.txt').read_text()
        votes,present,meanings=parse_evidence(text,self.raw,self.types,cut)
        return cut,text,votes,present,meanings

    def test_nominal_and_following_non_nominal_remain_separate(self):
        for number,expected in [(83,1),(84,0)]:
            with self.subTest(sessao=number):
                cut,_,votes,present,meanings=self.evidence(number)
                self.assertEqual(len(present),75)
                self.assertEqual(len(votes),expected)
                h=reconcile('6009',votes,present,meanings,self.ranges,[],TIME,cut)
                self.assertEqual(h['participacoesConferidas'],expected)
                self.assertEqual(h['comparecimentosConferidos'],1-expected)
                self.assertIsNone(h['naoJustificada'])

    def test_license_codes_need_effective_license_dates_before_classification(self):
        cut,_,votes,present,meanings=self.evidence(83)
        for register in ['LAP','LS']:
            code=next(str(r['codigoParlamentar']) for r in votes[0]['votos'] if r['siglaVotoParlamentar']==register)
            h=reconcile(code,votes,present,meanings,self.ranges,[],TIME,cut)
            self.assertEqual(h['pendentes'],1)
            license={'id':'verified','inicio':'2026-06-16','fim':'2026-06-16'}
            h=reconcile(code,votes,present,meanings,self.ranges,[{'licencas':[license],'fontes':['licencas']}],TIME,cut)
            self.assertEqual(h['justificativasRegistradas'],1)
            self.assertEqual(h['comparecimentosRegistrados'],0)
            self.assertIsNone(h['naoJustificada'])
