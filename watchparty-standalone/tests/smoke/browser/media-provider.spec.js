import { test, expect } from '@playwright/test';

async function createRoom(page, code) {
  await page.goto('/');
  await page.fill('#nameInput', 'MediaHost');
  await page.fill('#roomInput', code);
  await page.click('#createBtn');
  await expect(page.locator('#app')).toBeVisible();
}

test.describe('External media provider layer', () => {
  test('external media controls and resolved source metadata are visible to the host', async ({ page }) => {
    await createRoom(page, '812');
    await expect(page.locator('#mediaSourceInput')).toBeVisible();
    await expect(page.locator('#resolveMediaBtn')).toHaveText('Find Media');

    await page.route('**/api/media/resolve', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          title: 'Example Episode',
          results: [
            { url: 'https://cdn.example.test/episode/master.m3u8', type: 'hls', server: 'kiwi', quality: '1080p', audio: 'sub', subtitles: [] },
            { url: 'https://cdn.example.test/episode/backup.m3u8', type: 'hls', server: 'arc', quality: '720p', audio: 'dub', subtitles: [] }
          ]
        })
      });
    });

    await page.fill('#mediaSourceInput', 'https://example.test/watch/episode-1?ep=1');
    await page.click('#resolveMediaBtn');
    await expect(page.locator('#mediaSourceResults')).toBeVisible();
    await expect(page.locator('#mediaSourceSelect option')).toHaveCount(2);
    await expect(page.locator('#mediaMeta')).toContainText('Example Episode');
  });

  test('direct HLS source becomes authoritative room media state', async ({ page }) => {
    await createRoom(page, '813');
    await page.fill('#mediaSourceInput', 'https://example.com/episode/master.m3u8');
    await page.route('**/api/media/resolve', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, title: 'Direct HLS', results: [{ url: 'https://example.com/episode/master.m3u8', type: 'hls', server: 'direct', audio: null, subtitles: [] }] }) });
    });
    await page.click('#resolveMediaBtn');
    await expect(page.locator('#mediaSourceResults')).toBeVisible();
    await page.click('#loadMediaBtn');
    await expect(page.locator('#sourceModeLabel')).toHaveText('External media');
    await expect(page.locator('#mediaMeta')).toContainText(/Direct HLS|direct|HLS/i);
  });
});
