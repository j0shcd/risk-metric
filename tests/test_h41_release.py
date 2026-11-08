import unittest
from research.h41_release import extract, ExtractionError, TITLE
PRE='''<i>Release Date: December 29, 2022</i><pre>
5. TITLE
Millions of dollars
Assets, liabilities, and capital        Eliminations   Wednesday       Change since
                                            from     Dec 28, 2022  Wednesday Wednesday
                                       consolidation               Dec 21, 2022 Dec 29, 2021
Assets
Total assets                                  (0)     8,551,169      - 13,242 - 206,291
</pre>'''.replace('TITLE',TITLE)
TABLE='''<p>5. TITLE</p><p>Millions of dollars</p><table>
<tr><th rowspan="3">Assets, liabilities, and capital</th><th rowspan="3">Eliminations from consolidation</th><th rowspan="3">Wednesday<br>Dec 28, 2022</th><th colspan="2">Change since</th></tr>
<tr><th>Wednesday</th><th>Wednesday</th></tr><tr><th>Dec 21, 2022</th><th>Dec 29, 2021</th></tr>
<tr><td>Assets</td><td></td><td></td><td></td><td></td></tr>
<tr><td>Total assets</td><td>(0)</td><td>8,551,169</td><td>-13,242</td><td>-206,291</td></tr></table>'''.replace('TITLE',TITLE)
HTML='<i>Release Date: Thursday, December 29, 2022</i>'+TABLE
class TestExtractor(unittest.TestCase):
 def parse(self,s):return extract(s.encode(),'2022-12-29')
 def test_older_wrapped_header(self):
  old='Assets, liabilities, and capital        Eliminations   Wednesday       Change since\n                                            from     Dec 28, 2022  Wednesday Wednesday\n                                       consolidation               Dec 21, 2022 Dec 29, 2021'
  new='Eliminations Change since\nfrom Wednesday Wednesday Wednesday\nAssets, liabilities, and capital consolidation Dec 28, 2022 Dec 21, 2022 Dec 29, 2021'
  alternate='Eliminations from Wednesday Change since\nconsolidation Dec 28, 2022 Wednesday Wednesday\nAssets, liabilities, and capital Dec 21, 2022 Dec 29, 2021'
  self.assertEqual(self.parse(PRE.replace(old,alternate))['total_assets_usd_millions'],8551169)
  self.assertIn(old,PRE)
  self.assertEqual(self.parse(PRE.replace(old,new))['total_assets_usd_millions'],8551169)
  with self.assertRaises(ExtractionError):self.parse(PRE.replace(old,new.replace('Change since','Average')))
 def test_formats(self):
  for s in (PRE,HTML):
   r=self.parse(s);self.assertEqual(r['total_assets_usd_millions'],8551169);self.assertEqual(r['observation_date'],'2022-12-28');self.assertEqual(r['originality'],'not_asserted')
 def test_elimination_and_changes_not_level(self):
  for s in (PRE,HTML):
   r=self.parse(s.replace('(0)','(123)').replace('13,242','999,999'))
   self.assertEqual(r['total_assets_usd_millions'],8551169)
 def test_title_scope_decoy(self):
  decoy=TABLE.replace(TITLE,'Statement of Condition of Each Federal Reserve Bank').replace('8,551,169','999')
  self.assertEqual(self.parse('<p>Release Date: December 29, 2022</p>'+decoy+TABLE)['total_assets_usd_millions'],8551169)
  with self.assertRaises(ExtractionError):self.parse(HTML.replace(TITLE,'Reserve funds'))
 def test_header_columns_fail_closed(self):
  for s in (PRE,HTML):
   for old,new in [('Wednesday','Thursday'),('Change since','Level'),('Eliminations','Changes')]:
    with self.subTest(old=old),self.assertRaises(ExtractionError):self.parse(s.replace(old,new,1))
 def test_units_and_numbers(self):
  for s in (PRE,HTML):
   for old,new in [('Millions of dollars','Billions of dollars'),('8,551,169','8.55'),('8,551,169','NaN'),('8,551,169','-123'),('8,551,169','8,55,169')]:
    with self.subTest(new=new),self.assertRaises(ExtractionError):self.parse(s.replace(old,new))
 def test_release_observation_dates(self):
  for s in (PRE,HTML):
   for old,new in [('Release Date:','Notice date:'),('Dec 28, 2022','Jan 4, 2023'),('Dec 28, 2022','Dec 27, 2022')]:
    with self.subTest(new=new),self.assertRaises(ExtractionError):self.parse(s.replace(old,new))
   with self.assertRaises(ExtractionError):extract(s.encode(),'2022-12-30')
 def test_duplicates(self):
  with self.assertRaises(ExtractionError):self.parse(HTML+TABLE)
  with self.assertRaises(ExtractionError):self.parse(PRE+PRE[PRE.index('<pre>'):])
  with self.assertRaises(ExtractionError):self.parse(HTML.replace('</table>','<tr><td>Total assets</td><td>(0)</td><td>8551169</td></tr></table>'))
 def test_footer_and_notice_are_not_release(self):
  s=HTML+'<p>Last update: January 4, 2023</p><p>Correction announced January 5, 2023</p>'
  self.assertEqual(self.parse(s)['release_date'],'2022-12-29')
 def test_missing_title_and_row(self):
  for s in (PRE,HTML):
   with self.assertRaises(ExtractionError):self.parse(s.replace('Total assets','Total factors supplying reserve funds'))
 def test_target_requires_five_distinct_physical_cells(self):
  old='<td>8,551,169</td><td>-13,242</td><td>-206,291</td>'
  for new in ('<td colspan="3">123</td>','<td>123</td>','<td rowspan="2">123</td><td>-13,242</td><td>-206,291</td>'):
   with self.subTest(new=new),self.assertRaises(ExtractionError):self.parse(HTML.replace(old,new))
 def test_prior_headers_and_weekly_age(self):
  for s in (HTML,PRE):
   for old,new in [('Dec 21, 2022','Jan 4, 2023'),('Dec 21, 2022','Unknown'),('Dec 21, 2022','Dec 20, 2022'),('Dec 28, 2022','Dec 29, 2021')]:
    with self.subTest(new=new),self.assertRaises(ExtractionError):self.parse(s.replace(old,new))
 def test_exact_html_header_structure(self):
  for old,new in [('colspan="2"','colspan="3"'),('Wednesday<br>Dec 28, 2022','Change since Wednesday Dec 28, 2022'),('<th>Wednesday</th><th>Wednesday</th>','<th>Wednesday</th><th>Thursday</th>')]:
   with self.subTest(new=new),self.assertRaises(ExtractionError):self.parse(HTML.replace(old,new))
 def test_monday_holiday_and_current_age_bound(self):
  s=HTML.replace('Thursday, December 29, 2022','Monday, January 2, 2023')
  self.assertEqual(extract(s.encode(),'2023-01-02')['observation_date'],'2022-12-28')
  s=HTML.replace('Thursday, December 29, 2022','Thursday, January 5, 2023')
  with self.assertRaises(ExtractionError):extract(s.encode(),'2023-01-05')
 def test_spans_fail(self):
  with self.assertRaises(ExtractionError):self.parse(HTML.replace('rowspan="3"','rowspan="300"',1))
if __name__=='__main__':unittest.main()
