"""Sentinels for credential scope and bounded hosted jobs; no provider traffic."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicationSecurityTests(unittest.TestCase):
    def test_secrets_are_scoped_to_their_consuming_steps(self):
        text = (ROOT / '.github/workflows/daily-web-publish.yml').read_text()
        job, *steps = re.split(r'(?m)^      - name: ', text)
        self.assertNotIn('${{ secrets.', job)
        allowed = {
            'Require accepted model before refreshing dashboard': {'YOUTUBE_CHANNEL_IDS'},
            'Refresh caches from APIs + publish web export': {
                'YOUTUBE_API_KEY', 'YOUTUBE_CHANNEL_IDS', 'FRED_API_KEY',
                'WIKIMEDIA_API_TOKEN', 'WIKIMEDIA_API_USER_AGENT'},
            'Validate release and append prospective archive': {'RELEASE_ARCHIVE_UPLOAD_TOKEN'},
        }
        for step in steps:
            name = step.splitlines()[0]
            secrets = set(re.findall(r'\$\{\{ secrets\.([A-Z_]+) \}\}', step))
            self.assertEqual(secrets, allowed.get(name, set()), name)
            if '${{ github.token }}' in step:
                self.assertEqual(name, 'Commit updated web artifacts and caches')
        # Selection settings checked by the guard cannot be introduced only after it.
        for name in ('Require accepted model before refreshing dashboard',
                     'Refresh caches from APIs + publish web export'):
            self.assertIn('YOUTUBE_CHANNEL_IDS: ${{ secrets.YOUTUBE_CHANNEL_IDS }}',
                          next(step for step in steps if step.splitlines()[0] == name))

    def test_checkout_does_not_retain_write_credentials(self):
        text = (ROOT / '.github/workflows/daily-web-publish.yml').read_text()
        self.assertIn('permissions:\n  contents: read', text)
        self.assertIn('          persist-credentials: false', text)
        push = next(step for step in re.split(r'(?m)^      - name: ', text)[1:]
                    if step.startswith('Commit updated web artifacts and caches\n'))
        self.assertIn('GH_TOKEN: ${{ github.token }}', push)
        self.assertIn('credential.helper=', push)
        self.assertNotIn('https://x-access-token:', push)
        self.assertIn('push origin HEAD:main', push)

    def test_every_hosted_execution_job_has_an_explicit_deadline(self):
        for workflow in (ROOT / '.github/workflows').glob('*.yml'):
            for job in re.split(r'(?m)^  [a-z][a-z0-9-]*:\n', workflow.read_text())[1:]:
                if '    runs-on:' in job:
                    self.assertRegex(job, r'(?m)^    timeout-minutes: (?:[1-9]|[1-5][0-9]|60)$', workflow.name)


if __name__ == '__main__':
    unittest.main()
