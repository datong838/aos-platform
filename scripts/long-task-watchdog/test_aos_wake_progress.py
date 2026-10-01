import tempfile
import unittest
from pathlib import Path
from subprocess import run
from aos_wake_progress import observe, snapshot

class ProgressTest(unittest.TestCase):
    def snap(self, commit='a', at=100):
        return dict(repo='/repo', thread='thread', branch='m1', head=commit, code_commit=commit, code_time=at)

    def test_two_unchanged_wakes_require_review(self):
        a=observe({},self.snap(),'001',110)
        b=observe(a,self.snap(),'002',120)
        c=observe(b,self.snap(),'003',130)
        self.assertEqual(c['action'],'REVIEW_REQUIRED')
        self.assertEqual(c['unchanged_wakes'],2)

    def test_duplicate_or_old_event_does_not_increment(self):
        a=observe({},self.snap(),'002',110)
        self.assertEqual(observe(a,self.snap(),'002',900),a)
        self.assertEqual(observe(a,self.snap(),'001',900),a)

    def test_code_change_resets_counter(self):
        a=observe({},self.snap(),'001',2000)
        self.assertEqual(a['action'],'REVIEW_REQUIRED')
        b=observe(a,self.snap('b',2010),'002',2020)
        self.assertEqual(b['action'],'CONTINUE')
        self.assertEqual(b['unchanged_wakes'],0)

    def test_wrong_thread_or_repo_rejected(self):
        a=observe({},self.snap(),'001',110)
        for field in ('thread','repo'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                observe(a,dict(self.snap(),**{field:'other'}),'002',120)

    def test_wrong_branch_rejected(self):
        with self.assertRaises(ValueError):
            observe({},dict(self.snap(),branch='other'),'001',110)

    def test_document_commit_is_not_code_progress(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*args):
                return run(['git','-C',d,*args],check=True,capture_output=True,text=True).stdout.strip()
            git('init','-b','m1');git('config','user.name','test');git('config','user.email','test@invalid')
            p=Path(d)/'services';p.mkdir();(p/'feature.py').write_text('x=1\n')
            git('add','services/feature.py');git('commit','-m','code')
            original=snapshot(Path(d),'thread')['code_commit']
            (p/'notes.md').write_text('notes')
            git('add','services/notes.md');git('commit','-m','docs')
            s=snapshot(Path(d),'thread')
            self.assertEqual(s['code_commit'],original)
            self.assertNotEqual(s['head'],original)

if __name__=='__main__': unittest.main()
