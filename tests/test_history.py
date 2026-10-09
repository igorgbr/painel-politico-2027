import csv
import io
import unittest
from backend.sources.identity import cpf, match_camara, match_senado, ceap_identity_candidates
from backend.sources.history import parse_camara_projects, parse_camara_authors, parse_senado_projects, history_record, law_reference


def csv_file(rows):
    s=io.StringIO();w=csv.DictWriter(s, fieldnames=list(rows[0]),delimiter=';');w.writeheader();w.writerows(rows);return s.getvalue().encode('utf-8-sig')


class HistoryTests(unittest.TestCase):
    def test_ceap_candidate_ids_are_private_validated_and_not_name_based(self):
        import zipfile
        rows=[dict(cpf='529.982.247-25',ideCadastro='42'),dict(cpf='52998224725',ideCadastro='42'),dict(cpf='52998224725',ideCadastro='43'),dict(cpf='00000000000',ideCadastro='44')]
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as archive: archive.writestr('Ano-2026.csv',csv_file(rows))
        self.assertEqual(ceap_identity_candidates(raw.getvalue()),{'52998224725':{'42','43'}})
        # Ambiguidade exige consulta/confirmacão; o índice CEAP não produz vínculo.
        self.assertIsNone(match_camara({'cpf':'52998224725'},[{'id':42,'cpf':'00000000000'}]))
    def test_norm_requires_explicit_conversion_and_correct_project(self):
        project=dict(id='1',num='PL 1/2024')
        row=dict(id=1,siglaTipo='PL',numero=1,ano=2024,urnFinal=None,statusProposicao=dict(descricaoSituacao='Transformado em Norma Jurídica',despacho='Transformado na Lei Ordinária 14917/2024. DOU 08/07/24.'))
        self.assertEqual(law_reference(project,dict(dados=row)),'Lei Ordinária 14917/2024')
        for text in ['Aprovado na comissão. Lei Ordinária 14917/2024.', 'Apensado ao PL transformado na Lei Ordinária 14917/2024.']:
            # Exige que o despacho comece com a transformação do próprio projeto.
            row['statusProposicao']['despacho']=text
            self.assertIsNone(law_reference(project,dict(dados=row)))
        with self.assertRaises(ValueError): law_reference(dict(id='2',num='PL 1/2024'),dict(dados=row))
        tram=dict(codTipoTramitacao=251,despacho='Transformado na Lei Ordinária 14917/2024.')
        self.assertEqual(law_reference(project,dict(dados=row),[tram]),'Lei Ordinária 14917/2024')
        self.assertIsNone(law_reference(project,dict(dados=row),[dict(tram,codTipoTramitacao=100)]))
        self.assertIsNone(law_reference(project,dict(dados=row),[tram,dict(tram,despacho='Transformado na Lei Ordinária 15000/2025.')]))

    def test_norm_survives_reimport_and_updates_indicators(self):
        import tempfile
        from pathlib import Path
        from backend.store import Store
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.sqlite3')
            store.db.execute("INSERT INTO people VALUES('p-test','Teste')");store.db.commit()
            p=dict(id='1',num='PL 1/2024',situacao='Transformado em Norma Jurídica',norma=None,classificacao='outros',dataApresentacao='2024-01-01')
            h=history_record('camara','42',{'1':p},'2023-02-01','2026-10-05','2026-10-06T00:00:00Z',['https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-2024.csv'])
            store.save_norm('1','Lei Ordinária 14917/2024','https://dadosabertos.camara.leg.br/api/v2/proposicoes/1','2026-10-06T12:00:00Z')
            store.save_history('p-test',h)
            self.assertEqual(store.histories('p-test')[0]['aprov'],1)
            self.assertEqual(store.db.execute("SELECT value,coverage FROM indicators WHERE metric='aprov'").fetchone(),(1,'completa'))
            p.update(norma=None,classificacao='outros');store.save_history('p-test',h)
            self.assertEqual(store.histories('p-test')[0]['projetos'][0]['fonteNorma'],'https://dadosabertos.camara.leg.br/api/v2/proposicoes/1');store.close()
    def test_identity_requires_valid_cpf_and_unique_match(self):
        e={'cpf':'52998224725'}
        self.assertIsNone(cpf('00000000000'))
        self.assertIsNone(cpf('52998224726'))
        self.assertIsNone(match_camara(e,[{'nomeCivil':'Mesmo nome','cpf':'11111111111'}]))
        self.assertIsNone(match_camara(e,[{'id':1,'cpf':e['cpf']},{'id':2,'cpf':e['cpf']}]))
        self.assertEqual(match_camara(e,[{'id':3,'cpf':e['cpf']}])['id'],3)

    def test_senado_name_alone_insufficient(self):
        e={'nome':'Nome Exemplo','nascimento':'01/02/1980','ufNascimento':'SC'}
        p={'IdentificacaoParlamentar':{'NomeCompletoParlamentar':'NOME EXEMPLO'},'DadosBasicosParlamentar':{'DataNascimento':'1980-02-01','UfNaturalidade':'SC'}}
        self.assertIs(match_senado(e,[p]),p)
        self.assertIsNone(match_senado(e,[p,p]))
        p['DadosBasicosParlamentar']['UfNaturalidade']='SP'
        self.assertIsNone(match_senado(e,[p]))

    def test_conversion_needs_norm_archival_not_rejection(self):
        base={'id':'1','siglaTipo':'PL','numero':'1','ano':'2025','dataApresentacao':'2025-01-01','ementa':'Exemplo','ultimoStatus_descricaoSituacao':'Transformado em Norma Jurídica','urnFinal':''}
        rows=[base,dict(base,id='2',urnFinal='urn:lex:br:federal:lei:2025-02-01;15000'),dict(base,id='3',ultimoStatus_descricaoSituacao='Arquivada'),dict(base,id='4',ultimoStatus_descricaoSituacao='Rejeitada'),dict(base,id='5',siglaTipo='REQ'),dict(base,id='6',dataApresentacao='2022-12-31')]
        result=parse_camara_projects(csv_file(rows),'2023-02-01','2026-10-05')
        self.assertEqual(set(result),{'1','2','3','4'})
        self.assertEqual([result[str(i)]['classificacao']for i in range(1,5)],['outros','aprov','outros','neg'])

    def test_coauthors_deduplicated_and_entities_excluded(self):
        rows=[{'idProposicao':'1','uriAutor':'https://dadosabertos.camara.leg.br/api/v2/deputados/10'},{'idProposicao':'1','uriAutor':'https://dadosabertos.camara.leg.br/api/v2/deputados/10'},{'idProposicao':'1','uriAutor':'https://dadosabertos.camara.leg.br/api/v2/orgaos/10'}]
        self.assertEqual(parse_camara_authors(csv_file(rows),{'1':{}}),{'10':{'1'}})

    def test_senado_dedup_and_no_partial_approval(self):
        p={'id':1,'codigoMateria':100,'identificacao':'PL 1/2025','dataApresentacao':'2025-01-01','ementa':'Exemplo','situacaoAtual':'APROVADA NA COMISSÃO','normaGerada':None}
        rows=[p,p,dict(p,id=2,normaGerada='Lei Ordinária nº 15.001/2025'),dict(p,id=3,situacaoAtual='REJEITADA')]
        result=parse_senado_projects(rows,'2023-02-01','2026-10-05')
        h=history_record('senado','100',result,'2023-02-01','2026-10-05','2026-10-05T23:00:00-03:00',['https://legis.senado.leg.br/dadosabertos/processo.json'])
        self.assertEqual((h['total'],h['aprov'],h['neg']),(3,1,1))


if __name__=='__main__':unittest.main()
