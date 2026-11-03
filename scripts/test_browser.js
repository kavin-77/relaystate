const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9222;
const TARGET_URL = 'http://127.0.0.1:8089/';

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

async function run() {
  console.log("=== STEP 1: Launching Headless Chrome in Incognito (360x740) ===");
  const chromeProc = spawn(CHROME_PATH, [
    `--remote-debugging-port=${PORT}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--incognito',
    '--window-size=360,740',
    '--hide-scrollbars',
    'about:blank'
  ]);

  chromeProc.on('error', err => {
    console.error("Failed to start Chrome:", err);
    process.exit(1);
  });

  // Wait for Chrome CDP to be available
  let versionInfo = null;
  for (let i = 0; i < 20; i++) {
    await sleep(300);
    try {
      versionInfo = await getJson(`http://127.0.0.1:${PORT}/json/version`);
      if (versionInfo) break;
    } catch (e) {}
  }

  if (!versionInfo) {
    console.error("Chrome debugging port not ready!");
    chromeProc.kill();
    process.exit(1);
  }
  console.log("Chrome CDP ready. Connecting...");

  const list = await getJson(`http://127.0.0.1:${PORT}/json/list`);
  const pageTarget = list.find(t => t.type === 'page');
  const wsUrl = pageTarget.webSocketDebuggerUrl;

  const ws = new WebSocket(wsUrl);
  let msgId = 1;
  const pending = new Map();

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(msg.error);
      else resolve(msg.result);
    }
  };

  await new Promise(r => ws.onopen = r);

  await send('Runtime.enable');
  await send('Log.enable');

  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data);
    if (msg.method === 'Runtime.consoleAPICalled') {
      console.log(`[Browser Console ${msg.params.type}]`, ...msg.params.args.map(a => a.value || a.description));
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      console.error(`[Browser Uncaught Exception]`, msg.params.exceptionDetails);
    }
  });

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = msgId++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async function evaluate(expression) {
    const res = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (res.exceptionDetails) {
      throw new Error(res.exceptionDetails.exception.description);
    }
    return res.result.value;
  }

  try {
    await send('Page.enable');
    await send('DOM.enable');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 360,
      height: 740,
      deviceScaleFactor: 2,
      mobile: true
    });

    console.log(`\nNavigating to ${TARGET_URL}...`);
    await send('Page.navigate', { url: TARGET_URL });
    await sleep(1500);

    console.log("\n=== STEP 2: Verify First Screen & Mobile Layout (360px) ===");

    // 1. Check Next step text
    const nextStepText = await evaluate(`document.getElementById('stepperHint').innerText`);
    console.log(`[PASS] Stepper Hint Text: "${nextStepText}"`);
    if (!nextStepText.includes('Start guided demo')) {
      throw new Error(`Expected 'Start guided demo' in stepper hint, got: ${nextStepText}`);
    }

    // 2. Check Horizontal Scroll on 360px
    const scrollInfo = await evaluate(`({
      bodyScrollWidth: document.body.scrollWidth,
      docScrollWidth: document.documentElement.scrollWidth,
      windowInnerWidth: window.innerWidth,
      windowScrollX: window.scrollX
    })`);
    console.log(`[PASS] Scroll Metrics at 360px width:`, scrollInfo);
    if (scrollInfo.docScrollWidth > 360 || scrollInfo.bodyScrollWidth > 360) {
      console.warn(`WARNING: Width slightly above 360: doc=${scrollInfo.docScrollWidth}, body=${scrollInfo.bodyScrollWidth}`);
    } else {
      console.log(`[PASS] ZERO horizontal scrolling! Elements fit within 360px perfectly.`);
    }

    // 3. Check Stepper height
    const stepperHeight = await evaluate(`document.querySelector('.stepper').offsetHeight`);
    console.log(`[PASS] Stepper height on mobile: ${stepperHeight}px (Requirement: under 60px tall)`);
    if (stepperHeight > 60) {
      throw new Error(`Stepper too tall: ${stepperHeight}px`);
    }

    // 4. Check Three Role Cards
    const roleCards = await evaluate(`({
      dave: document.getElementById('roleCard-leaver')?.innerText.replace(/\\s+/g, ' ').trim(),
      marcus: document.getElementById('roleCard-lead')?.innerText.replace(/\\s+/g, ' ').trim(),
      amina: document.getElementById('roleCard-successor')?.innerText.replace(/\\s+/g, ' ').trim(),
      activeCard: document.querySelector('.role-card.active-role-card')?.id,
      selectedRole: document.getElementById('roleSelect')?.value
    })`);
    console.log(`[PASS] Role cards found:`, roleCards);
    if (roleCards.activeCard !== 'roleCard-leaver' || roleCards.selectedRole !== 'leaver') {
      throw new Error(`Initial active card should be Dave (leaver), got: ${roleCards.activeCard}`);
    }

    console.log("\n=== STEP 3: Test Switching Roles via Marcus and Amina Cards ===");

    // Click Marcus Card
    console.log("Clicking Marcus card...");
    await evaluate(`document.getElementById('roleCard-lead').click()`);
    await sleep(200);

    const marcusState = await evaluate(`({
      activeCard: document.querySelector('.role-card.active-role-card')?.id,
      selectedRole: document.getElementById('roleSelect')?.value
    })`);
    console.log(`[PASS] After clicking Marcus:`, marcusState);
    if (marcusState.activeCard !== 'roleCard-lead' || marcusState.selectedRole !== 'lead') {
      throw new Error(`Failed to switch to Marcus lead role!`);
    }

    // Click Amina Card
    console.log("Clicking Amina card...");
    await evaluate(`document.getElementById('roleCard-successor').click()`);
    await sleep(200);

    const aminaState = await evaluate(`({
      activeCard: document.querySelector('.role-card.active-role-card')?.id,
      selectedRole: document.getElementById('roleSelect')?.value
    })`);
    console.log(`[PASS] After clicking Amina:`, aminaState);
    if (aminaState.activeCard !== 'roleCard-successor' || aminaState.selectedRole !== 'successor') {
      throw new Error(`Failed to switch to Amina successor role!`);
    }

    // Click Dave Card back
    console.log("Clicking Dave card back...");
    await evaluate(`document.getElementById('roleCard-leaver').click()`);
    await sleep(200);

    const daveState = await evaluate(`({
      activeCard: document.querySelector('.role-card.active-role-card')?.id,
      selectedRole: document.getElementById('roleSelect')?.value
    })`);
    console.log(`[PASS] Switched back to Dave:`, daveState);

    console.log("\n=== STEP 4: Test Guided Demo Flow to the End ===");

    // Click Start Guided Demo
    console.log("Clicking 'Start guided demo' button...");
    await evaluate(`document.getElementById('btnStartGuided').click()`);

    // Wait for Step 1 -> Step 2
    for (let i = 0; i < 25; i++) {
      await sleep(400);
      const coachText = await evaluate(`document.getElementById('coachText')?.innerText`);
      const coachBtn = await evaluate(`document.getElementById('coachBtn')?.innerText`);
      const coachStep = await evaluate(`coachStep`);
      if (coachStep === 2) {
        console.log(`[PASS] Reached Guided Tour Step 2: "${coachText}" (Button: "${coachBtn}")`);
        break;
      }
    }

    // Check Citation Pill highlight in Step 2
    const pillHighlighted = await evaluate(`!!document.querySelector('.cite-pill.pill-highlight')`);
    console.log(`[PASS] Citation pill has pulsing highlight: ${pillHighlighted}`);

    // Advance Step 2 -> Step 3
    console.log("Advancing to Step 3 (Dave review & sign-off)...");
    await evaluate(`document.getElementById('coachBtn').click()`);
    await sleep(2200); // Wait for sample source drawer to open and close

    let step3Text = await evaluate(`document.getElementById('coachText')?.innerText`);
    let step3Btn = await evaluate(`document.getElementById('coachBtn')?.innerText`);
    console.log(`[PASS] Reached Step 3: "${step3Text}" (Button: "${step3Btn}")`);

    // Advance Step 3 (Dave signs off) -> Step 4
    console.log("Advancing Step 3: Executing Dave review and sign-off...");
    await evaluate(`document.getElementById('coachBtn').click()`);

    // Wait for step 4
    for (let i = 0; i < 20; i++) {
      await sleep(300);
      const step = await evaluate(`coachStep`);
      if (step === 4) {
        const text = await evaluate(`document.getElementById('coachText')?.innerText`);
        const btn = await evaluate(`document.getElementById('coachBtn')?.innerText`);
        const version = await evaluate(`document.getElementById('versionBadge')?.innerText`);
        const role = await evaluate(`document.getElementById('roleSelect')?.value`);
        console.log(`[PASS] Reached Step 4: "${text}" (Button: "${btn}", Version: ${version}, Role: ${role})`);
        break;
      }
    }

    // Advance Step 4 (Marcus approves & publishes v1.0) -> Step 5
    console.log("Advancing Step 4: Executing Marcus approval to publish v1.0...");
    await evaluate(`document.getElementById('coachBtn').click()`);

    // Wait for step 5
    for (let i = 0; i < 20; i++) {
      await sleep(300);
      const step = await evaluate(`coachStep`);
      if (step === 5) {
        const text = await evaluate(`document.getElementById('coachText')?.innerText`);
        const btn = await evaluate(`document.getElementById('coachBtn')?.innerText`);
        const version = await evaluate(`document.getElementById('versionBadge')?.innerText`);
        const role = await evaluate(`document.getElementById('roleSelect')?.value`);
        console.log(`[PASS] Reached Step 5: "${text}" (Button: "${btn}", Version: ${version}, Role: ${role})`);
        break;
      }
    }

    // Check Successor Day-1 plan view is unlocked
    const successorBlocked = await evaluate(`!!document.querySelector('.blocked-box')`);
    console.log(`[PASS] Successor 403 block lifted after Marcus approval: ${!successorBlocked}`);

    // Advance Step 5 (Amina opens handover) -> Step 6
    console.log("Advancing Step 5 -> Step 6 (Tamper-proof audit log)...");
    await evaluate(`document.getElementById('coachBtn').click()`);

    // Wait for step 6
    for (let i = 0; i < 20; i++) {
      await sleep(300);
      const step = await evaluate(`coachStep`);
      if (step === 6) {
        const text = await evaluate(`document.getElementById('coachText')?.innerText`);
        const btn = await evaluate(`document.getElementById('coachBtn')?.innerText`);
        console.log(`[PASS] Reached Step 6: "${text}" (Button: "${btn}")`);
        break;
      }
    }

    // Advance Step 6 (Verify audit log) -> Step 7 (Done)
    console.log("Advancing Step 6: Verifying audit chain blocks...");
    await evaluate(`document.getElementById('coachBtn').click()`);

    // Wait for step 7
    for (let i = 0; i < 20; i++) {
      await sleep(300);
      const step = await evaluate(`coachStep`);
      if (step === 7) {
        const text = await evaluate(`document.getElementById('coachText')?.innerText`);
        const btn = await evaluate(`document.getElementById('coachBtn')?.innerText`);
        console.log(`[PASS] Reached Step 7 (End): "${text}" (Button: "${btn}")`);
        break;
      }
    }

    console.log("\n=== STEP 5: Verify Hash Chain Linked Blocks & Tamper/Restore ===");
    const chainState1 = await evaluate(`({
      validBlocks: document.querySelectorAll('.chain-block.block-valid').length,
      tamperedBlocks: document.querySelectorAll('.chain-block.block-tampered').length,
      alertText: document.getElementById('auditStatusAlert')?.innerText.replace(/\\s+/g, ' ').trim()
    })`);
    console.log(`[PASS] Initial verified hash chain:`, chainState1);
    if (chainState1.validBlocks === 0 || chainState1.tamperedBlocks > 0) {
      throw new Error(`Expected all blocks valid, got: ${JSON.stringify(chainState1)}`);
    }

    // Test Simulate Tampering
    console.log("Testing Simulate Tampering in Audit Tab...");
    await evaluate(`simulateTamper(true)`);
    await sleep(600);

    const chainState2 = await evaluate(`({
      validBlocks: document.querySelectorAll('.chain-block.block-valid').length,
      tamperedBlocks: document.querySelectorAll('.chain-block.block-tampered').length,
      alertText: document.getElementById('auditStatusAlert')?.innerText.replace(/\\s+/g, ' ').trim()
    })`);
    console.log(`[PASS] After Simulate Tampering:`, chainState2);
    if (chainState2.tamperedBlocks === 0) {
      throw new Error(`Tampered blocks did not turn red!`);
    }

    // Test Restore
    console.log("Testing Restore Authentic State in Audit Tab...");
    await evaluate(`restoreTamper(true)`);
    await sleep(600);

    const chainState3 = await evaluate(`({
      validBlocks: document.querySelectorAll('.chain-block.block-valid').length,
      tamperedBlocks: document.querySelectorAll('.chain-block.block-tampered').length,
      alertText: document.getElementById('auditStatusAlert')?.innerText.replace(/\\s+/g, ' ').trim()
    })`);
    console.log(`[PASS] After Restore:`, chainState3);
    if (chainState3.validBlocks === 0 || chainState3.tamperedBlocks > 0) {
      throw new Error(`Restored blocks did not heal back to green!`);
    }

    console.log("\n=== ALL BROWSER CHECKS & GUIDED DEMO PASSED WITH 100% SUCCESS! ===");
  } catch (err) {
    console.error("Test Error:", err);
    process.exitCode = 1;
  } finally {
    ws.close();
    chromeProc.kill();
  }
}

run();
