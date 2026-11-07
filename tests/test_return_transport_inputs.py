import unittest
import numpy as np


class WarmupBoundaryTests(unittest.TestCase):
    def test_prior_warmup_is_selected_without_extra_origins(self):
        import pandas as pd
        from research.return_transport_runner import common_frame
        dates=pd.date_range('2014-12-31','2022-12-31',freq='ME').strftime('%Y-%m-%d').tolist()
        frame=pd.DataFrame({'Date':pd.date_range('2012-01-31','2022-12-31',freq='ME').strftime('%Y-%m-%d'), 'value':np.arange(132)})
        selected=common_frame(frame.to_csv(index=False).encode(),dates)
        self.assertEqual(selected.Date.tolist(),dates)
        self.assertEqual(selected.value.tolist(),list(range(35,132)))
        cases=[frame.drop(index=5),frame.iloc[:-1],pd.concat([frame,frame.iloc[-1:]]),frame.iloc[::-1]]
        for text in ['2023-01-31','2022-12-30','2022-12-31 12:00:00','2022-12-31T00:00:00Z']:
            bad=frame.copy();bad.loc[131,'Date']=text;cases.append(bad)
        for bad in cases:
            with self.subTest(tail=bad.Date.iloc[-1]),self.assertRaises((ValueError,TypeError)):
                common_frame(bad.to_csv(index=False).encode(),dates)
