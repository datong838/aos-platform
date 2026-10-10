import importlib.util, io, os, tarfile
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('prepare_api159', Path(__file__).with_name('prepare_api159_source.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as tar:
        for name, kind in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            if kind == tarfile.REGTYPE:
                item.size = 3
                tar.addfile(item, io.BytesIO(b'abc'))
            else:
                item.linkname = 'scripts/entry.py'
                tar.addfile(item)
    return out.getvalue()

@pytest.mark.parametrize('name', ['../x','/tmp/x','scripts/../x','scripts//x','./scripts/x','other/x'])
def test_unsafe_name(name):
    with pytest.raises(ValueError):
        m.archive_files(archive([(name, tarfile.REGTYPE)]))

@pytest.mark.parametrize('kind', [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.FIFOTYPE,tarfile.CHRTYPE])
def test_links_and_special(kind):
    with pytest.raises(ValueError):
        m.archive_files(archive([('scripts/x', kind)]))

def test_duplicate():
    with pytest.raises(ValueError, match='DUPLICATE'):
        m.archive_files(archive([('scripts/x',tarfile.REGTYPE)]*2))

def test_extra_directory_scope():
    with pytest.raises(ValueError, match='SCOPE'):
        m.archive_files(archive([('other',tarfile.DIRTYPE),('scripts/x',tarfile.REGTYPE)]))

def test_exact_export_and_drift(tmp_path):
    os.chmod(tmp_path,0o700)
    raw=archive([('scripts/x',tarfile.REGTYPE)])
    expected=m.manifest(m.archive_files(raw));root=tmp_path/'source'
    assert m.materialize(raw,root,expected)['service_start_attempted'] is False
    assert m.verify(root,expected)
    with pytest.raises(ValueError,match='EXISTING'):
        m.materialize(raw,root,expected)
    (root/'scripts/x').write_bytes(b'bad')
    with pytest.raises(ValueError,match='MANIFEST'):
        m.verify(root,expected)

def test_insecure_export_rejected(tmp_path):
    os.chmod(tmp_path,0o700)
    raw=archive([('scripts/x',tarfile.REGTYPE)]);expected=m.manifest(m.archive_files(raw));root=tmp_path/'source'
    m.materialize(raw,root,expected);os.chmod(root/'scripts/x',0o666)
    with pytest.raises(ValueError,match='PERMISSIONS'):
        m.verify(root,expected)

def test_omission_and_migration_subset():
    files={'scripts/x':b'abc','services/aos-api/alembic.ini':b'ini'}
    with pytest.raises(ValueError,match='MIGRATION'):
        m.require_migration_subset(files,{})
    m.require_migration_subset(files,m.manifest({'services/aos-api/alembic.ini':b'ini'}))
    with pytest.raises(ValueError,match='MANIFEST'):
        m.materialize(archive([('scripts/x',tarfile.REGTYPE)]),Path('/unused'),m.manifest(files))

def test_private_parent_required(tmp_path):
    os.chmod(tmp_path,0o755);raw=archive([('scripts/x',tarfile.REGTYPE)])
    with pytest.raises(ValueError,match='PRIVATE_PARENT'):
        m.materialize(raw,tmp_path/'source',m.manifest(m.archive_files(raw)))
    assert not (tmp_path/'source').exists()

def test_deep_directory_permissions(tmp_path):
    os.chmod(tmp_path,0o700)
    raw=archive([('services/aos-api/aos_api/deep/module.py',tarfile.REGTYPE)])
    expected=m.manifest(m.archive_files(raw));root=tmp_path/'source'
    assert m.materialize(raw,root,expected)['files']==1
    assert all(path.stat().st_mode & 0o077 == 0 for path in root.rglob('*'))
