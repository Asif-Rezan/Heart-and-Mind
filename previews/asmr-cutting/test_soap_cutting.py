import unittest
import numpy as np
import soap_cutting as s

class CuttingGeometryTests(unittest.TestCase):
    def test_contact_bottom_and_detachment_share_one_clock(self):
        for k in range(s.CUTS):
            self.assertAlmostEqual(s.knife_state(s.t_contact(k))[1],s.YTOP,places=6)
            self.assertAlmostEqual(s.knife_state(s.t_bottom(k))[1],s.YBOT,places=6)
            self.assertIsNone(s.slice_state(k,s.t_detach(k)-.001))
            dx,hop,angle=s.slice_state(k,s.t_land(k))
            slot=s.PILE_X+(s.CUTS-1-k)*s.SPACING
            self.assertAlmostEqual(s.xcut(k)+dx,slot)
            self.assertAlmostEqual(hop,0,places=6)
            self.assertLess(s.t_land(k),s.TAKE_SECONDS)
    def test_portrait_sixty_second_thirty_fps_timeline(self):
        self.assertEqual((s.W,s.H,s.FPS),(720,1280,30))
        self.assertAlmostEqual(s.TAKE_SECONDS,10)
        self.assertEqual(s.NFRAMES,round(s.TOTAL*s.FPS))
        self.assertEqual(s.TOTAL,60)
    def test_geometry_cache_includes_box_extents(self):
        a=s.box_polys(30,80,'rem',True)
        b=s.box_polys(30,130,'rem',True)
        self.assertIsNot(a,b)
    def test_color_variants_remain_deterministic(self):
        s.configure_take(0)
        first=np.array(s.render_scene(3.2))
        s.configure_take(1)
        second=np.array(s.render_scene(3.2))
        self.assertFalse(np.array_equal(first,second))
        s.configure_take(0)
        self.assertTrue(np.array_equal(first,np.array(s.render_scene(3.2))))

if __name__=='__main__': unittest.main()
