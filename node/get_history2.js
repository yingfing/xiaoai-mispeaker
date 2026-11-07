// 查小爱对话记录（先正确初始化 hardware）
const { MiAccount, MiTokenStore, MiNAService } = require("F:/pnpm/node_modules/@bjyy/miservice/src");

const TOKEN = "C:/Users/Administrator/.mi.token";

async function main() {
  const store = new MiTokenStore(TOKEN);
  const account = new MiAccount("_", "_", store);
  account.token = await store.load_token();

  if (!account.token) {
    console.error("没有 token");
    process.exit(1);
  }

  const mina = new MiNAService(account);

  // 关键：先初始化设备映射，填充 device2hardware
  const devices = await mina.device_list();
  const dev = devices[0];
  const deviceId = dev.deviceID;
  const hardware = dev.hardware;

  // 手动设置 hardware（这是 URL 里必需的）
  mina.hardware = hardware;
  mina.device2hardware = { [deviceId]: hardware };

  console.log(`设备: ${dev.name} (${hardware})`);
  console.log(`deviceID: ${deviceId}`);
  console.log("");

  // 查对话
  try {
    const msgs = await mina.fetchHistoryMsgs({ limit: 10, filterAnswer: false });
    console.log(`=== 最近 ${msgs.length} 条对话 ===`);
    if (!msgs || msgs.length === 0) {
      console.log("(没有记录)");
      return;
    }
    for (const m of msgs) {
      const t = m.timestamp ? new Date(m.timestamp).toLocaleString("zh-CN") : "?";
      console.log(`\n[${t}]`);
      console.log(`  问: ${m.question || "(空)"}`);
      console.log(`  答: ${m.answer || "(空)"}`);
    }
  } catch (e) {
    console.error("查询失败:", e.message);
  }
}

main().catch((e) => {
  console.error("错误:", e.message);
  process.exit(1);
});
