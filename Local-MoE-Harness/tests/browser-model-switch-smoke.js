const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  try {
    await page.goto('http://127.0.0.1:5180', {waitUntil: 'networkidle'});
    await page.getByRole('button', {name: 'Change model'}).click();
    const panel = page.locator('#model-panel');
    await panel.waitFor({state: 'visible'});
    const registry = await page.evaluate(async () => (await fetch('/api/models')).json());
    const cards = await page.locator('.model-card').allTextContents();
    if (cards.length === 0) throw new Error('model registry rendered no cards');

    const qwen = registry.registry.find((model) => model.id === 'qwen36-nvfp4');
    const qwenCard = cards.find((text) => text.includes('Qwen3.6')) || '';
    if (!qwen) throw new Error('Qwen3.6 registry entry is missing');
    if (qwen.active && !(qwenCard.includes('Ready') && qwenCard.includes('Active'))) throw new Error('Qwen active card state is inconsistent');

    const gpt = registry.registry.find((model) => model.id === 'gpt-oss-20b');
    const gptCardText = cards.find((text) => text.includes('GPT-OSS 20B')) || '';
    if (!gpt) throw new Error('GPT-OSS registry entry is missing');
    if (gpt.installed && gpt.selectable && !gpt.active && !(gptCardText.includes('Installed') && gptCardText.includes('Switch'))) throw new Error('GPT-OSS installed switch action is missing');

    const coder = registry.registry.find((model) => model.id === 'qwen3-coder-30b-fp8');
    const coderCard = cards.find((text) => text.includes('Qwen3 Coder 30B A3B FP8')) || '';
    if (!coder) throw new Error('Qwen3 Coder registry entry is missing');
    if (coder.host_platform === 'windows') {
      if (coder.selectable) throw new Error('Qwen3 Coder must remain platform-blocked on Windows');
      if (!coderCard.includes('Compatibility blocked')) throw new Error('Windows Coder compatibility block is not visible');
    } else {
      if (coder.validation !== 'validated') throw new Error('Linux Qwen3 Coder is not marked validated');
      if (!coder.selectable) throw new Error('Linux Qwen3 Coder is not selectable');
      if (coder.active && !(coderCard.includes('Ready') && coderCard.includes('Active'))) throw new Error('active Qwen3 Coder card state is inconsistent');
      if (!coder.active && coder.installed && !(coderCard.includes('Installed') && coderCard.includes('Switch'))) throw new Error('installed Qwen3 Coder switch action is missing');
    }

    const gemma = registry.registry.find((model) => model.id === 'gemma4-26b-q4_0-gguf');
    const gemmaCard = cards.find((text) => text.includes('Gemma 4 26B A4B Q4_0')) || '';
    if (!gemma) throw new Error('Gemma Q4_0 registry entry is missing');
    if (gemma.active && !(gemmaCard.includes('Ready') && gemmaCard.includes('Active'))) throw new Error('active Gemma card state is inconsistent');
    if (!gemma.active && gemma.installed && gemma.selectable && !(gemmaCard.includes('Installed') && gemmaCard.includes('Switch'))) throw new Error('installed selectable Gemma card state is inconsistent');

    const ramLabel = await page.locator('#metrics article').nth(2).locator('span').textContent();
    if (ramLabel !== 'RAM used / total') throw new Error(`ambiguous RAM label: ${ramLabel}`);
    for (const id of ['host-volume', 'wsl-virtual-disk']) {
      const storageText = await page.locator(`#${id}`).textContent();
      if (storageText && storageText !== '—' && !storageText.includes('GiB')) throw new Error(`ambiguous storage unit for ${id}: ${storageText}`);
    }

    if (gpt.installed && gpt.selectable && !gpt.active) {
      let dismissed = false;
      page.once('dialog', async (dialog) => { dismissed = dialog.message().includes('GPT-OSS 20B'); await dialog.dismiss(); });
      const gptCard = page.locator('.model-card').filter({hasText: 'GPT-OSS 20B'});
      await gptCard.getByRole('button', {name: 'Switch'}).click();
      if (!dismissed) throw new Error('model-switch confirmation was not shown');
    }

    const screenshotPath = path.join(__dirname, '..', 'output', 'playwright', 'model-selector.png');
    fs.mkdirSync(path.dirname(screenshotPath), {recursive: true});
    await page.screenshot({path: screenshotPath, fullPage: true});
    console.log('browser-model-switch: PASS (registry, platform policy, labels, actions)');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exit(1); });
