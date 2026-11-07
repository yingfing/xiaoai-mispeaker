// 查小爱对话记录（按实际字段结构：records[].query / answers）
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
  const devices = await mina.device_list();
  const dev = devices[0];

  mina.hardware = dev.hardware;
  mina.device2hardware = { [dev.deviceID]: dev.hardware };

  console.log(`设备: ${dev.name} (${dev.hardware})\n`);

  // 直接调 getConversations 拿原始 records
  const conv = await mina.getConversations({ limit: 20 });
  const records = conv.records || [];

  console.log(`=== 共 ${records.length} 条记录 ===\n`);

  if (records.length === 0) {
    console.log("原始响应:", JSON.stringify(conv).substring(0, 500));
    return;
  }

  for (const r of records) {
    let t = "?";
    if (r.time) {
      t = new Date(r.time * 1000).toLocaleString("zh-CN");
    }
    console.log(`[${t}]`);
    console.log(`  问: ${r.query || "(空)"}`);

    // answers 是数组
    if (r.answers && r.answers.length) {
      for (const a of r.answers) {
        const txt = a.content || a.text || a.answer || JSON.stringify(a).substring(0, 100);
        console.log(`  答: ${txt}`);
      }
    } else {
      console.log(`  答: (无)`);
    }
    console.log();
  }

  // 输出一条原始记录看结构
  console.log("\n=== 原始记录结构（第一条）===");
  console.log(JSON.stringify(records[0], null, 2).substring(0, 800));
}

main().catch((e) => {
  console.error("错误:", e.message);
  process.exit(1);
});
