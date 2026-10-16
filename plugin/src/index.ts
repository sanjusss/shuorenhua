import { Plugin } from "@opencode/plugin"
import { readFileSync } from "node:fs"
import { join } from "node:path"

const SKILL_ID = "shuorenhua"
// 包根 = 仓库根；本文件在 `plugin/src/` 下，往上两级是 `SKILL.md`
const SKILL_PATH = join(import.meta.dir, "..", "..", "SKILL.md")

// 三段固定文本，全部是纯静态字符串。
// 禁止拼接时间戳、计数器等每次调用会变化的内容，否则会击穿 `provider` 的前缀缓存。
const HEADER = "以下是每次回复必须遵守的中文写作规则（shuorenhua 技能正文）："
const REMINDER = "\n\n回复、写作必须遵守 shuorenhua 的规则。"

export default Plugin.define({
  id: "shuorenhua",
  async setup(ctx) {
    // 一、注册技能：本地没有 `shuorenhua` 技能时，用包内文件注册一份。
    // 本地已有同名技能时不覆盖（本地优先）。
    await ctx.skill.transform((editor) => {
      if (editor.list().some((s) => s.id === SKILL_ID)) return
      let content: string
      try {
        content = readFileSync(SKILL_PATH, "utf8")
      } catch {
        return
      }
      editor.add({
        id: SKILL_ID,
        name: "说人话：中文写作规则与检查",
        description:
          "中文写作必须遵守的规则与检查流程：用词、术语、句式、拟人化、超长句、中英混杂。适用于对话回复、Markdown 文档、代码注释。",
        path: SKILL_PATH,
        content,
      })
    })

    // 二、每次主对话模型调用做两件事。这两处修改只影响当次发出的请求，
    // 不进持久化历史，用户界面显示的消息是原文。
    // context hook 抛错会导致整个会话失败，必须捕获后跳过。
    await ctx.session.hook("context", async (event) => {
      // 1. 技能正文注入 `system` 末尾
      try {
        // 注意：`list()` 返回 `{ location, data }`，技能列表在 `data` 字段
        const result = (await ctx.skill.list()) as { data?: { id?: string; content?: string }[] }
        const skill = (result.data ?? []).find((s) => s.id === SKILL_ID)
        if (!skill?.content) return
        event.system.push({ type: "text", text: `${HEADER}\n\n${skill.content}` })
      } catch {
        // 跳过本次注入
      }

      // 2. 提醒句追加到请求里的所有用户消息。每次调用都做同样的追加，
      // 同一条消息在多次调用间渲染一致，前缀缓存才能命中。
      try {
        for (const message of event.messages) {
          if (message.role !== "user") continue
          const parts = message.content as { type?: string; text?: string }[]
          const lastText = [...parts].reverse().find((p) => p.type === "text" && typeof p.text === "string")
          if (lastText) lastText.text += REMINDER
          else parts.push({ type: "text", text: REMINDER })
        }
      } catch {
        // 跳过本次追加
      }
    })
  },
})
