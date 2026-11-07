// 查对话记录，尝试不同时间范围
const { MiAccount, MiTokenStore, MiNAService } = require("F:/pnpm/node_modules/@bjyy/miservice/src");

const TOKEN = "C:/Users/Administrator/.mi.token";

async function main() {
  const store = new MiTokenStore(TOKEN);
  const account = new MiAccount("_", "_", store);
  account.token = await store.load_token();

  const mina = new MiNAService(account);
  const devices = await mina.device_list();
  const dev = devices[0];
  mina.hardware = dev.hardware;
  mina.device2hardware = { [dev.deviceID]: dev.hardware };

  console.log(`设备: ${dev.name}\n`);

  const now = Math.floor(Date.now() / 1000);

  // 尝试多种参数组合
  const tries = [
    { name: "默认", opts: { limit: 20 } },
    { name: "今天", opts: { limit: 20, timestamp: now } },
    { name: "往前1小时", opts: { limit: 20, timestamp: now - 3600 } },
    { name: "往前1天", opts: { limit: 20, timestamp: now - 86400 } },
    { name: "往前7天", opts: { limit: 50, timestamp: now - 86400 * 7 } },
  ];

  for (const t of tries) {
    try {
      const conv = await mina.getConversations(t.opts);
      const n = (conv.records || []).length;
      console.log(`[${t.name}] records=${n}, 响应=${JSON.stringify(conv).substring(0, 120)}`);
      if (n > 0) {
        console.log("\n=== 找到记录 ===");
        for (const r of conv.records) {
          const ts = r.time ? new Date(r.time * 1000).toLocaleString("zh-CN") : "?";
          console.log(`\n[${ts}]`);
          console.log(`  问: ${r.query || "(空)"}`);
          const ans = (r.answers || []).map(a => a.content || a.text || "").join(" | ");
          console.log(`  答: ${ans || "(无)"}`);
        }
        break;
      }
    } catch (e) {
      console.log(`[${t.name}] 失败: ${e.message.substring(0, 100)}`);
    }
    await new Promise(r => setTimeout(r, 500));
  }

  // 最后输出一次原始 getConversations 的返回
  console.log("\n=== 原始返回 ===");
  try {
    const conv = await mina.getConversations({ limit: 10 });
    console.log(JSON.stringify(conv, null, 2).substring(0, 600));
  } catch (e) {
    console.log(e.message.substring(0, 200));
  }
}

main().catch((e) => {
  console.error("错误:", e.message);
  process.exit(1);
});
