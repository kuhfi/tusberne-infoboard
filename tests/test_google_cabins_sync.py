"""Offline self-checks for Google Sheets read-only importer and weekly safety."""
import copy
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts' if (ROOT/'scripts').exists() else ROOT/'pi'))
from cabins_overrides import game_key, effective_plan
from pi_google_cabins_sync import build_new_store, parse_revision_rows

NOW=datetime(2026,11,11,10,30,tzinfo=ZoneInfo('Europe/Berlin'))
WEEK='2026-11-09'
A={'date':'2026-11-14','time':'09:30','kind':'Meisterschaft','league':'Bezirksliga',
   'home':'tus BERNE 1.C (A1)','away':'GW Eimsbüttel 1.C (A1)',
   'home_cabin':'1','guest_cabin':'3','sr_cabin':'SR1','festival':False}
B={'date':'2026-11-14','time':'11:00','kind':'Meisterschaft','league':'Kreisklasse',
   'home':'tus BERNE 4.C','away':'Nordlichter 1.C',
   'home_cabin':'2','guest_cabin':'4','sr_cabin':'SR2','festival':False}
BASE={'schema_version':1,'generated_at':'2026-11-10T14:20:55+01:00',
  'period':{'weeks':[{'start':WEEK,'end':'2026-11-15'}]},'games':[A,B]}


def sheets(mode='partial',revision=1,details=None,week=WEEK,count=None):
    details=details if details is not None else []
    if count is None: count=len(details)
    meta=[[week,mode,str(revision),'2026-11-11T10:30:00+01:00','hash',str(count)]]
    return [meta,details if mode=='partial' else [],details if mode=='locked' else []]


class GoogleImporterTest(unittest.TestCase):
    def test_empty_sheet_keeps_automatic(self):
        st,rec,rev=parse_revision_rows(BASE,[[],[],[]],NOW)
        self.assertEqual((st,rec,rev),(WEEK,None,None))

    def test_only_guest_cabin_overridden(self):
        details=[[WEEK,'1',game_key(A),'guest_cabin','4','now']]
        st,rec,rev=parse_revision_rows(BASE,sheets(details=details),NOW)
        self.assertEqual(rec['changes'][game_key(A)],{'guest_cabin':'4'})
        store={'schema_version':1,'weeks':{st:rec}}
        eff=effective_plan(BASE,store,NOW)
        self.assertEqual(eff['games'][0]['guest_cabin'],'4')
        self.assertEqual(eff['games'][0]['home_cabin'],'1')
        self.assertEqual(eff['games'][0]['sr_cabin'],'SR1')
        self.assertEqual(eff['games'][1],B)

    def test_source_changed_does_not_apply_to_other_game(self):
        details=[[WEEK,'1',game_key(A),'guest_cabin','4','now']]
        st,rec,_=parse_revision_rows(BASE,sheets(details=details),NOW)
        new=copy.deepcopy(BASE);new['games'][0]['time']='10:00'
        out=effective_plan(new,{'weeks':{st:rec}},NOW)
        self.assertEqual(out['games'][0]['guest_cabin'],'3')
        self.assertEqual(out['manual_weeks'][st]['unmatched'],1)

    def test_full_week_lock_freezes_all_games(self):
        edited=copy.deepcopy(A);edited['guest_cabin']='4'
        row=[WEEK,'3','1',edited['date'],edited['time'],edited['kind'],edited['league'],edited['home'],edited['away'],edited['home_cabin'],edited['guest_cabin'],edited['sr_cabin'],'false']
        st,rec,rev=parse_revision_rows(BASE,sheets('locked',3,[row]),NOW)
        eff=effective_plan(BASE,{'weeks':{st:rec}},NOW)
        self.assertEqual(len(eff['games']),1)
        self.assertEqual(eff['games'][0]['guest_cabin'],'4')
        self.assertEqual(eff['manual_weeks'][st]['mode'],'locked')

    def test_entire_week_can_be_empty_lock(self):
        st,rec,rev=parse_revision_rows(BASE,sheets('locked',2,[],count=0),NOW)
        self.assertEqual(rec['games'],[])
        self.assertEqual(effective_plan(BASE,{'weeks':{st:rec}},NOW)['games'],[])

    def test_automatic_revision_unlocks_and_cannot_downgrade(self):
        before={'schema_version':1,'weeks':{WEEK:{'mode':'locked','games':[],'origin':'google_sheets'}},
                'google_cabins_sync':{'sheet_id':'X','revisions':{WEEK:2}}}
        rows=sheets('automatic',3,[],count=0)
        saved,changed,start,rev=build_new_store(BASE,rows,before,NOW,'X')
        self.assertTrue(changed)
        self.assertNotIn(WEEK,saved['weeks'])
        with self.assertRaisesRegex(ValueError,'zurückgesetzt'):
            build_new_store(BASE,sheets('automatic',1,[],count=0),before,NOW,'X')

    def test_absent_metadata_cannot_delete_previous_revision(self):
        prev={'schema_version':1,'weeks':{},'google_cabins_sync':{'sheet_id':'X','revisions':{WEEK:3}}}
        with self.assertRaisesRegex(ValueError,'verschwunden'):
            build_new_store(BASE,[[],[],[]],prev,NOW,'X')

    def test_manual_local_edit_never_overwritten(self):
        prev={'schema_version':1,'weeks':{WEEK:{'mode':'locked','games':[]}}}
        with self.assertRaisesRegex(ValueError,'lokale Wochenkorrekturen'):
            build_new_store(BASE,sheets('automatic',1,[],count=0),prev,NOW)

    def test_revisions_must_be_complete(self):
        for mode in ('partial','locked'):
            with self.assertRaisesRegex(ValueError,'Unvollständige'):
                parse_revision_rows(BASE,sheets(mode,1,[],count=1),NOW)

    def test_bad_cabin_does_not_import(self):
        data=[[WEEK,'1',game_key(A),'guest_cabin','SR1','now']]
        with self.assertRaisesRegex(ValueError,'Unzulässige'):
            parse_revision_rows(BASE,sheets(details=data),NOW)

    def test_duplicate_game_keys_rejected(self):
        duplicate=copy.deepcopy(BASE);duplicate['games'].append(copy.deepcopy(A))
        data=[[WEEK,'1',game_key(A),'guest_cabin','4','now']]
        with self.assertRaisesRegex(ValueError,'Mehrdeutiges'):
            parse_revision_rows(duplicate,sheets(details=data),NOW)

    def test_next_week_ignores_last_week(self):
        next_week=copy.deepcopy(BASE)
        next_week['period']['weeks']=[{'start':'2026-11-16','end':'2026-11-22'}]
        next_week['games']=[]
        st,rec,rev=parse_revision_rows(next_week,sheets(),datetime(2026,11,16,0,5,tzinfo=ZoneInfo('Europe/Berlin')))
        self.assertEqual(st,'2026-11-16')
        self.assertIsNone(rec)

    def test_incoming_partial_revision_newer_than_cache(self):
        old={'schema_version':1,'weeks':{},'google_cabins_sync':{'sheet_id':'X','revisions':{WEEK:1}}}
        data=[[WEEK,'2',game_key(A),'guest_cabin','4','now']]
        new,changed,st,rev=build_new_store(BASE,sheets('partial',2,data),old,NOW,'X')
        self.assertTrue(changed);self.assertEqual(new['weeks'][st]['revision'],2)
        same,changed2,_,_=build_new_store(BASE,sheets('partial',2,data),new,NOW,'X')
        self.assertFalse(changed2)

if __name__=='__main__':unittest.main()