const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const checks = {};
checks.secureContext = isSecureContext;
checks.webLocks = !!navigator.locks;
checks.mediaAPI = !!navigator.mediaDevices?.getUserMedia;
for (let i = 0; i < 120; i++) {
  if (document.querySelectorAll('[data-save]').length >= 10) break;
  await wait(500);
}
await wait(3500);
checks.title = document.title.includes('IELTS');
checks.body = document.body.innerText.includes('学习');
checks.fields = document.querySelectorAll('[data-save]').length;
checks.navigation = document.querySelectorAll('button,a').length > 20;
checks.errors = [];
const root = await fetch('index.html');
checks.localHome = root.status === 200 && (await root.text()).includes('daily-study-state');
const image = await fetch('app-icon-192.png');
checks.image = image.ok && (await image.arrayBuffer()).byteLength > 1000;
const audioPaths = [...document.querySelectorAll('audio[src],audio source[src]')].map(x => x.getAttribute('src')).filter(x => x && !x.startsWith('http'));
checks.audioPaths = audioPaths.length;
if (audioPaths.length) {
  const audio = await fetch(audioPaths[0], {headers:{Range:'bytes=0-1023'}});
  checks.audioRange = audio.status === 206 && (await audio.arrayBuffer()).byteLength === 1024;
  const suffix = await fetch(audioPaths[0], {headers:{Range:'bytes=-512'}});
  checks.audioSeek = suffix.status === 206 && (await suffix.arrayBuffer()).byteLength === 512;
}
const old = localStorage.getItem('ielts-native-ci-probe');
checks.restartPersistence = old === 'native-ci-v1';
localStorage.setItem('ielts-native-ci-probe','native-ci-v1');
checks.storage = localStorage.getItem('ielts-native-ci-probe') === 'native-ci-v1';
const field = [...document.querySelectorAll('textarea[data-save]')].find(x => !x.disabled && !x.readOnly);
if (field) {
  checks.editableField = field.dataset.save;
  checks.answerRestored = field.value === 'Native iPad offline persistence test';
  field.value = 'Native iPad offline persistence test';
  field.dispatchEvent(new Event('input',{bubbles:true}));
  field.dispatchEvent(new Event('change',{bubbles:true}));
  await wait(2500);
  checks.answerStored = Object.keys(localStorage).some(k => (localStorage.getItem(k)||'').includes('Native iPad offline persistence test'));
}
// Exercise the actual WKDownload path with a Blob-backed backup.
const link = document.createElement('a');
link.href = URL.createObjectURL(new Blob(['{"nativeBackupProbe":true}'],{type:'application/json'}));
link.download = 'native-backup-test.json'; document.body.append(link); link.click();
await wait(2000);
link.remove();
checks.passed = checks.secureContext && checks.webLocks && checks.title && checks.fields >= 10 && checks.navigation && checks.localHome && checks.image && checks.audioRange && checks.audioSeek && checks.storage && checks.answerStored;
return checks;
