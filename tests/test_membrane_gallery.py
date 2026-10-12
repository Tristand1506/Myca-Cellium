"""Membrane comparisons preserve membership, source regions and scope limits."""
import copy
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import membrane_gallery as membrane
import review_metadata as meta
from test_site_gallery import fixture
from validate_site import Page


class MembraneGalleryTests(unittest.TestCase):
    def setUp(self):
        self.manifest=fixture()
        self.org=meta.default_metadata()
        self.org['collections']=[
            {'id':'membranes','name':'Membranes','assets':['1'*64,'2'*64,'3'*64],'details':[]},
            {'id':'line-a','name':'A renamed group','assets':['3'*64],'details':['view-membrane']},
            {'id':'line-b','name':'Same source in another direction','assets':['3'*64],'details':[]},
        ]
        self.org['details']=[{'id':'view-membrane','title':'Exact selected panel','asset_sha256':'2'*64,'rect':[.1,.2,.4,.8]}]
        self.config={'schema_version':1,'source_collection':'membranes','directions':[
            {'id':'petal','collection_id':'line-a','title':'Petal','summary':'Separate sheets.','basis':'documented candidate'},
            {'id':'lace','collection_id':'line-b','title':'Lace','summary':'Porous tissue.','basis':'documented candidate'},
            {'id':'vascular','collection_id':'line-c','title':'Vascular','summary':'Branching support.','basis':'documented candidate'},
        ]}

    def test_direction_membership_uses_stable_ids_and_is_many_to_many(self):
        groups=membrane.direction_items(self.org,self.config)
        self.assertEqual([i['id'] for i in groups[0]['items']],['view-membrane','3'*64])
        self.assertEqual(groups[1]['items'][0]['id'],'3'*64)
        self.assertEqual(groups[2]['items'],[])
        self.assertEqual([i['id'] for i in groups[3]['items']],['1'*64,'2'*64])

    def test_saved_region_does_not_assign_whole_parent_or_rewrite_bounds(self):
        item=membrane.direction_items(self.org,self.config)[0]['items'][0]
        self.assertEqual(item['detail'],self.org['details'][0])
        self.assertIn('2'*64,[i['id'] for i in membrane.direction_items(self.org,self.config)[-1]['items']])
        page=membrane.membrane_page(self.manifest,self.org,self.config)
        self.assertIn('No new bitmap or R/C ID',page)
        self.assertIn('[0.1, 0.2, 0.4, 0.8]',page)

    def test_scope_and_crop_parent_caveats_remain_visible(self):
        page=membrane.membrane_page(self.manifest,self.org,self.config)
        self.assertIn('Only leg proportions; inherit parent caveat',page)
        self.assertIn('Do not inherit cap height',page)
        self.assertIn('Crop-parent limitations',page)
        self.assertIn('working experimental groups',page)
        self.assertIn('no new approval',page)

    def test_archived_parents_are_excluded_with_history_count(self):
        self.org['archived']=['2'*64,'3'*64]
        groups=membrane.direction_items(self.org,self.config)
        self.assertEqual(groups[0]['items'],[])
        self.assertEqual(groups[0]['archived_count'],2)
        page=membrane.membrane_page(self.manifest,self.org,self.config)
        self.assertNotIn('data-compare-id="view-membrane"',page)
        self.assertIn('2 archived membership(s)',page)

    def test_no_scripts_still_has_directions_originals_and_region_provenance(self):
        page=membrane.membrane_page(self.manifest,self.org,self.config)
        parsed=Page(page)
        self.assertEqual(len(parsed.ids),len(set(parsed.ids)))
        self.assertIn('direction-petal',parsed.ids)
        self.assertTrue(parsed.images)
        self.assertTrue(all(i['loading']=='lazy' and i['alt'] for i in parsed.images))
        self.assertIn('No active studies assigned',page)
        self.assertIn('data-compare-select',page)

    def test_region_preview_has_an_undistorted_no_script_original_fallback(self):
        region=self.org['details'][0]
        asset=self.manifest['assets'][1]
        preview=membrane.preview(asset,region,region['title'])
        enhanced,fallback=preview.split('<noscript>',1)
        self.assertIn('class="membrane-preview" hidden',enhanced)
        self.assertIn('class="membrane-region"',enhanced)
        self.assertNotIn('membrane-region',fallback)
        self.assertNotIn('style=',fallback)
        self.assertIn('Full original shown.',fallback)
        self.assertEqual(Page(enhanced).images[0]['src'],Page(fallback).images[0]['src'])
        self.assertNotIn('<noscript>',membrane.preview(asset,None,region['title']))

    def test_titles_are_escaped_and_no_input_is_mutated(self):
        self.org['details'][0]['title']='<script>bad</script>'
        self.config['directions'][0]['title']='<strong>topic</strong>'
        before=copy.deepcopy((self.manifest,self.org,self.config))
        page=membrane.membrane_page(self.manifest,self.org,self.config)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;',page)
        self.assertNotIn('<script>bad',page)
        self.assertEqual((self.manifest,self.org,self.config),before)

    def test_unregistered_art_keeps_its_status_and_hash_identity(self):
        self.manifest['references'][2]['asset_sha256']=[]
        page=membrane.membrane_page(self.manifest,self.org,self.config)
        self.assertIn('Unregistered artwork',page)
        self.assertIn('data-compare-id="'+('3'*64)+'"',page)
        self.assertIn('No recorded feature approval',page)

    def test_private_public_fields_rejected_before_render(self):
        self.org['notes']={'secret':'private'}
        with self.assertRaises(ValueError):
            membrane.membrane_page(self.manifest,self.org,self.config)

    @unittest.skipUnless(shutil.which('node'), 'Node required for membrane controls')
    def test_comparison_controls(self):
        subprocess.run(['node',str(Path(__file__).with_name('test_membrane_controls.js'))],check=True)

    def test_layout_rejects_bad_ids_duplicate_sources_and_private_approval_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'data').mkdir(); path=root/membrane.CONFIG_PATH
            bad=[]
            for key,value in [('id','unsorted'),('collection_id','membranes'),('basis',{}),('title','C:\\private\\file')]:
                config=copy.deepcopy(self.config); config['directions'][0][key]=value; bad.append(config)
            config=copy.deepcopy(self.config); config['directions'].append(config['directions'][0]); bad.append(config)
            config=copy.deepcopy(self.config); config['approved']=True; bad.append(config)
            for config in bad:
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    membrane.load_layout(root)
            path.write_text(json.dumps(self.config))
            self.assertEqual(membrane.load_layout(root),self.config)
            path.unlink()
            self.assertEqual(membrane.load_layout(root)['directions'],[])


if __name__=='__main__':
    unittest.main()
