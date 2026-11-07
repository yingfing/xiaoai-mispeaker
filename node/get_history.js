// 查小爱最近对话记录
const path = require("path");
const { MiAccount, MiTokenStore, MiNAService } = require("F:/pnpm/node_modules/@bjyy/miservice/src");

const TOKEN = "C:/Users/Administrator/.mi.token";
const DID = "979227698";

async function main() {
  const store = new MiTokenStore(TOKEN);
  const account = new MiAccount("_", "_", store);
  account.token = await store.load_token();

  if (!account.token) {
    console.error("没有 token");
    process.exit(1);
  }

  const mina = new MiNAService(account);

  // 先拿设备列表确定 deviceID
  const devices = await mina.device_list();
  console.log("设备列表:", JSON.stringify(devices, null, 2).substring(0, 800));
  console.log("");

  if (!devices || !devices.length) {
    console.error("没有设备");
    process.exit(1);
  }

  const deviceId = devices[0].deviceID;
  console.log("deviceID:", deviceId);
  console.log("");

  // 查最新对话
  try {
    const msgs = await mina.get_latest_ask(deviceId);
    console.log("=== 最近对话 ===");
    if (!msgs || msgs.length === 0) {
      console.log("(没有记录)");
    } else {
      for (const m of msgs) {
        const time = m.timestamp ? new Date(m.timestamp).toLocaleString("zh-CN") : "?";
        console.log(`\n[${time}]`);
        console.log(`  问: ${m.question || "(空)"}`);
        console.log(`  答: ${m.answer || "(空)"}`);
      }
    }
  } catch (e) {
    console.error("查询失败:", e.message);
  }
}

main().catch((e) => {
  console.error("错误:", e.message);
  process.exit(1);
});
