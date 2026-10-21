import json
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gazerefine.interactive import normalize_fixations, read_fixations, samples_to_fixations
from gazerefine.model import affinity_neighbors, propagate_neighbors


class PromptTests(unittest.TestCase):
    def test_single_and_equal_duration_gaze_has_nonzero_weight(self):
        self.assertEqual(normalize_fixations([[.5,.5,200]])[0,2],1)
        np.testing.assert_equal(normalize_fixations([[.4,.5,200],[.6,.5,200]])[:,2],[1,1])

    def test_duration_transform_and_reject_invalid_input(self):
        np.testing.assert_allclose(normalize_fixations([[.4,.5,100],[.6,.5,300]])[:,2],[0,1])
        np.testing.assert_equal(normalize_fixations([[.4,.5,100],[.6,.5,300]],False)[:,2],[1,1])
        for points in [[], [[1.1,.5,1]], [[.5,float('nan'),1]], [[.5,.5,0]]]:
            with self.assertRaises(ValueError):normalize_fixations(points)

    def test_csv_units_and_image_selection(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'gaze.csv';p.write_text('x,y,duration\n25,50,150\n')
            np.testing.assert_allclose(read_fixations(p,100,200,'pixels'),[[.25,.25,150]])
            with self.assertRaises(ValueError):read_fixations(p,100,200,'normalized')
            p.write_text('IMAGE,CURRENT_FIX_INDEX,CURRENT_FIX_X,CURRENT_FIX_Y,CURRENT_FIX_DURATION\na.jpg,2,.2,.3,100\nb.jpg,1,.7,.8,200\na.jpg,1,.4,.5,50\n')
            rows=read_fixations(p,100,200,image_name='a.dcm')
            self.assertEqual(len(rows),2);self.assertEqual(rows[0],[.4,.5,50])

    def test_dwell_groups_never_bridge_outside_or_long_gaps(self):
        sample=[[.5,.5,0],[.51,.5,60],[.5,.51,120],[1.2,.5,150],
                [.5,.5,200],[.5,.5,260],[.5,.5,320],[.5,.5,700]]
        groups=samples_to_fixations(sample)
        self.assertEqual(len(groups),2);self.assertEqual([g[2] for g in groups],[120,120])
        with self.assertRaises(ValueError):samples_to_fixations([[.5,.5,100],[.5,.5,0]])


class AffinityTests(unittest.TestCase):
    def test_chunked_neighbors_match_full_matrix(self):
        torch.manual_seed(17);p=torch.randn(2,67,23);s=torch.rand(2,67)
        normal=F.normalize(p,dim=-1);val,idx=torch.bmm(normal,normal.transpose(1,2)).topk(7,dim=-1)
        expected=(F.softmax(val/.05,dim=-1)*torch.gather(s[:,None,:].expand(-1,67,-1),2,idx)).sum(-1)
        actual=propagate_neighbors(s,affinity_neighbors(p,7,.05,chunk_size=13))
        torch.testing.assert_close(actual,expected,rtol=1e-5,atol=1e-6)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.serve_app import AppServer
        cls.server=AppServer(('127.0.0.1',0));cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()

    def request(self,path,data=None,headers=None):
        r=urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',data=None if data is None else json.dumps(data).encode(),headers=headers or {})
        return urllib.request.urlopen(r)

    def test_local_auth_and_cross_origin_rejection(self):
        with self.request('/api/config') as response:self.assertIn('token',json.load(response))
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/fixations',{'samples':[]},{'Content-Type':'application/json'})
        self.assertEqual(cm.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/config',headers={'Origin':'https://example.org'})
        self.assertEqual(cm.exception.code,403)

    def test_fixation_endpoint_and_static_path_boundary(self):
        headers={'Content-Type':'application/json','X-GazeRefine-Token':self.server.token}
        with self.request('/api/fixations',{'samples':[[.5,.5,0],[.5,.5,120]]},headers) as response:
            self.assertEqual(len(json.load(response)['fixations']),1)
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/../README.md')
        self.assertEqual(cm.exception.code,404)

    def test_desktop_image_session_and_captured_gaze_transfer(self):
        self.server.set_session(Image.new('RGB',(16,12),'gray'),[[.4,.5,200]],'example.png')
        headers={'Content-Type':'application/json','X-GazeRefine-Token':self.server.token}
        with self.request('/api/session',headers=headers) as response:
            session=json.load(response)['session']
        self.assertTrue(session['image'].startswith('data:image/png;base64,'))
        self.assertEqual(session['name'],'example.png')
        captured=[];self.server.on_capture=captured.append
        with self.request('/api/capture',{'revision':session['revision'],'fixations':[[.5,.5,120]],'samples':[[.5,.5,0],[.5,.5,120]]},headers) as response:
            self.assertTrue(json.load(response)['synced'])
        self.assertEqual(captured[0]['fixations'],[[.5,.5,120]])
        self.server.on_capture=None

    def test_capture_cannot_attach_to_a_changed_desktop_image(self):
        self.server.set_session(Image.new('RGB',(8,8)),[],'first.png')
        old=self.server.session_version
        self.server.set_session(Image.new('RGB',(8,8)),[],'second.png')
        headers={'Content-Type':'application/json','X-GazeRefine-Token':self.server.token}
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request('/api/capture',{'revision':old,'fixations':[[.5,.5,100]],'samples':[]},headers)
        self.assertEqual(cm.exception.code,409)


if __name__=='__main__':unittest.main()
