const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://bsapi.colourlabs.net';
const CONFIG_PATH = path.join(__dirname, 'config.json');
const HOUR_MS = 60 * 60 * 1000;

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error('Missing config.json. Copy config.example.json to config.json and add your bot token.');
  }

  const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
  const config = JSON.parse(raw);

  if (!config.token) {
    throw new Error('config.json must include a bot token under the "token" field.');
  }

  return config;
}

function formatTime(date) {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

async function postMessage(token, content) {
  const response = await fetch(`${BASE_URL}/api/posts/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bot ${token}`,
    },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Failed to post message: ${response.status} ${response.statusText} - ${body}`);
  }

  return response.json();
}

async function sendHourlyMessage(token) {
  const now = new Date();
  const content = `Its ${formatTime(now)} what are you doing bojansocial?`;
  console.log(`[${now.toISOString()}] Sending message: ${content}`);
  const result = await postMessage(token, content);
  console.log('Message posted:', result);
}

async function main() {
  const config = loadConfig();

  if (typeof fetch !== 'function') {
    throw new Error('This bot requires Node.js 18 or newer with built-in fetch.');
  }

  await sendHourlyMessage(config.token);

  setInterval(() => {
    sendHourlyMessage(config.token).catch((error) => {
      console.error('Hourly message failed:', error);
    });
  }, HOUR_MS);

  console.log('bojantis is running. A message is scheduled every hour.');
}

main().catch((error) => {
  console.error('Failed to start bojantis:', error);
  process.exit(1);
});
