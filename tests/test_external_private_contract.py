"""Independent sink oracle: numeric source/member/CSV and scored results stay private.

Public fixture manifests and registration are metadata-only exemptions. This is
not a hostile concurrent-filesystem sandbox; all numerical writers are inventoried.
"""
import ast
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research import external_equity_fixture as f, monthly_portability as m


class PrivateSinkContract(unittest.TestCase):
    def test_all_numeric_sinks_share_path_matrix_before_source_read(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory).resolve(); private=base/'private';private.mkdir()
            (base/'alias').symlink_to(private, target_is_directory=True)
            cases=[('traversal',private/'..'/'outside',False),
                   ('outside',base/'outside',False),('root',private,False),
                   ('root_alias',private/'child'/'..',False),
                   ('symlink_ancestor',base/'alias'/'child',False),
                   ('valid',private/'child',True),
                   ('inside_alias',private/'other'/'..'/'child',True)]
            for sink in ('acquire','derive','run'):
                for name,output,allowed in cases:
                    with self.subTest(sink=sink,case=name), patch.object(f,'PRIVATE_ROOT',private), patch.object(m,'PRIVATE_ROOT',private):
                        # A successful boundary reaches this source-read witness;
                        # rejected paths must never reach it or create output.
                        witness=RuntimeError('SOURCE_READ_WITNESS')
                        if sink=='acquire':
                            with patch.object(f,'download',side_effect=witness) as read:
                                self.probe(lambda:f.acquire(output,base/'metadata.json'),allowed,read)
                        elif sink=='derive':
                            with patch.object(Path,'open',side_effect=witness) as read:
                                self.probe(lambda:f.derive(output,base/'metadata.json'),allowed,read)
                        else:
                            with patch.object(Path,'read_bytes',return_value=b'{}'), patch.object(m,'registration',return_value={}), patch.object(m,'publish'), patch.object(m,'write_packet'), patch.object(Path,'open',side_effect=witness) as read:
                                self.probe(lambda:m.run(base/'source',base/'registration',output),allowed,read)
                            if allowed:(private/'child').rmdir()
                        self.assertFalse((base/'outside').exists())

    def probe(self,call,allowed,read):
        if allowed:
            with self.assertRaisesRegex(RuntimeError,'SOURCE_READ_WITNESS'):call()
            read.assert_called_once()
        else:
            with self.assertRaises(ValueError):call()
            read.assert_not_called()

    def test_writer_inventory_has_no_unreviewed_sinks(self):
        # Inventory underlying publishing primitives, not helper callers alone.
        for module,expected in [(f,{'_write_once','acquire','derive'}),(m,{'run','main'})]:
            tree=ast.parse(inspect.getsource(module));actual=set()
            for node in tree.body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    for call in ast.walk(node):
                        if isinstance(call,ast.Call):
                            name=getattr(call.func,'id',getattr(call.func,'attr',''))
                            if name in {'_write_once','write_packet','publish','write'}:actual.add(node.name)
            self.assertEqual(actual,expected)
        # main's register writes metadata only; run owns all model numerics.

    def test_source_cannot_alias_reserved_output(self):
        with tempfile.TemporaryDirectory() as directory:
            private=Path(directory).resolve();output=private/'run'
            for source in (output,output/'source.csv',output/'nested'/'..'/'source.csv'):
                with self.subTest(source=source), patch.object(m,'PRIVATE_ROOT',private), patch.object(Path,'read_bytes',return_value=b'{}'), patch.object(m,'registration',return_value={}), patch.object(Path,'open') as read:
                    with self.assertRaisesRegex(ValueError,'alias'):m.run(source,private/'reg',output)
                    read.assert_not_called();self.assertFalse(output.exists())
