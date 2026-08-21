# 《琵琶曲》琵琶曲 AI 短片工业化制作手册（T2VA 纯文字版 · v2.1.1）

> 依据《琵琶曲_AI短片制作方案》与《AI古风短片工业化制作手册升级 Prompt》（MIX.txt）升级。
> 版本：v2.1.1（试点修订版）｜ 生成模式：MiniMax H3 **T2VA**（纯文字，全程无参考图）｜ 成片 60-90 秒
> 视频提示词库：同目录《琵琶曲_视频提示词库.md》（18 条，每条 6000-7000 字符，H3 单条上限 7000 内）；已导出 18 个 TXT（`prompt/txt/`，每镜一个，可直接上传）

## v2.1.1 修订要点（电视剧剧本化收尾）

1. **男主完全不出镜**：男主观感转为"观众视角"，画面只展示女主（见 3.4）
2. **说话不唱歌**（3.11）：女主全程只**说话/独白**（电视剧式对白 + 感情词汇衬托），禁止旋律性演唱；prompt 内明写 `The woman never sings; she only speaks her lines with emotion like a TV drama actress`
3. **远景可有人、禁人脸**（3.9）：远景/全景允许出现人物（身体、剪影、背影、局部），但禁止任何面部细节，防模型远处人脸崩坏
4. **story_context 全局主题注入**：每条 prompt 开头内嵌片名《琵琶曲》/主题"若只如初遇"/`Shot N of 18`/上下镜承接与落幅/贯穿意象（满月、乌篷船、红灯笼、月白裙青纱、白玉琵琶）/时空层，解决"镜头无关联、无整体主题"
5. **朝代锚定规则**（3.10）：全片锁定唐代服饰发型建筑，负面词防清装
6. **背景配乐**：`non_diegetic_music` 字段完整描述（3.11）
7. **单镜头 prompt 6000-7000 字符**（≤7000），信息密度最大化
8. **歌词定位（v2.1.1）**：歌词为**灵感参考**，非逐句对应——镜头按剧情重创，不再直接画面化歌词意象（史书/古城/王朝意象已删，改「人化时间」段）
9. **第七段「历史长河」→「时光无声」**（镜 13-15）：四季流转环绕同一女子，岁月仅以环境+神情表达、人脸五官零变化（2.1 阶段 B 延伸）
10. **镜 06 事件化**：双舫琴声相和→指尖微顿→继续相和（「相知」从意象变为事件）
11. **批次调整**：镜 13 露脸→第 2 批；第 3 批仅剩 01/03/07/14/15/18

---

# 第一部分：项目总纲

## 1.1 项目定位

| 维度 | 内容 |
|------|------|
| 类型 | 古风音乐短片 / 东方爱情电影式 MV（歌曲视觉化） |
| 目标观众 | 国风音乐爱好者、古装影视受众、B站/抖音 16-35 岁 |
| 情绪关键词 | 相思、清冷、怅惘、初见之美、盛唐华美、离别之痛、千年回望、若只如初遇 |
| 视觉风格 | 盛唐东方电影美学：月白与金红并置、轻纱质感、35mm 胶片、浅景深、慢镜头 |
| 参考电影感 | 《长安三万里》诗意构图；《妖猫传》盛唐宫宴光影；《琵琶行》江夜孤寂 |
| 年代锚定 | **唐代（唐宋之际）**，服饰、建筑、器物一律唐代样式（见 3.10 防清规则） |

**一句话定位**：一支"琵琶女子与故人跨越时空的相思"为内核的东方电影式古风 MV。**画面中只出现女主一人，男主是"被思念的画外人"，他的视线由镜头（观众）代替。**

## 1.2 故事核心分析

- **主线冲突**：空间（浔阳江与长安）与时间（盛唐与千年后）双重离别之下，一段琴音牵起的相遇与诀别。
- **人物关系**：琵琶女子与白衣故人——初遇于长安夜市琴声，相知于江上双舫，相伴于宫宴盛世，终因离别天各一方；多年后唯余女子独奏，四季在她身侧流转（时光无声），终走入暮色，时光倒转回初遇。**男主全程不出镜：他是她琴声里、目光里、回忆里的存在，观众取代他的位置去看她。**
- **情绪变化**：孤寂（江夜）→ 心动（初遇）→ 静好（相知）→ 极盛（宫宴）→ 骤落（雨夜诀别）→ 苍凉（多年独奏）→ 空茫（时光无声）→ 释然（若只如初遇）。
- **高潮位置**：第五段"哭的梨花带雨"（情绪顶点）与第四段"盛世相伴"（视觉顶点）对置——"最盛与最痛"。
- **最终情感落点**：不悲不怨——"今生与你，若只如初遇"：时间不可逆，但相遇的美被永远留住。结尾必须落在"美好定格"而非"悲伤"。

## 1.3 音乐与画面关系（歌词灵感对照 · 非逐句对应）

| 歌词 | 画面 | 动作 | 情绪 | 镜头 |
|------|------|------|------|------|
| 前奏（琵琶独奏+古琴） | 浔阳江夜、满月、乌篷船 | 船缓缓划过江面 | 孤寂静谧 | 航拍大远景、慢降 |
| 人间琴悠扬 | 女子独坐船头弹琵琶 | 手指轻拨琴弦 | 清冷专注 | 中景推近 |
| 姑娘把谁记心上 | 女子抬头望月 | 目光望向远方 | 思念 | 侧脸近景 |
| 南来与北往 | 长安夜市、万盏灯笼、人流 | 人群流动 | 繁华躁动 | 大全景 |
| 美人取情寄琵琶 | 楼上女子弹琴，镜头（观众）自街心仰望 | 女子回眸望向镜头 | 惊艳初动 | 中景、仰角 |
| 东船与西舫 | 女子船尾弹琴，镜头如另一船随行 | 琴声随水而行 | 静谧温柔 | 全景横移 |
| 琴音袅袅于心上 | 女子船尾拨弦，对面船琴声相和 | 指尖微顿、继续相和 | 相知 | 手部特写 |
| 卿和了胡旋 | 宫宴胡旋舞 | 舞袖旋转 | 盛极之欢 | 全景、环绕 |
| 君作汉宫琵琶语 | 女子独奏，镜头缓推（观众在席间） | 琵琶声起 | 美好 | 中景缓推 |
| 姑娘不胜酒力 | 夜雨空楼、独饮 | 举杯、垂首 | 悲恸将至 | 全景、慢拉 |
| 哭的梨花带雨 | 泪落琴弦 | 泪滴滑落、琴音顿止 | 最高潮之痛 | 特写（泪+弦） |
| 弹一首琵琶曲 | 多年后江边再弹 | 指尖重落琴弦 | 苍凉释然 | 中景横移 |
| 叹离愁争朝夕 | 同一江岸亭四季流转 | 四季在身侧流过 | 时光流逝 | 中景、叠化 |
| 史书一页未起（灵感） | 空亭归暮，女子走入暮色 | 放琴、望江、离去 | 释然怅惘 | 全景→大远景 |
| 今生与你 | 回到初见灯火之下 | 女子转身回眸 | 心动重现 | 中景、环绕 |
| 若只如初遇 | 回眸微笑、时间停住 | 定格微笑 | 美好永恒 | 特写、静帧感 |

> ⚠️ v2.1 注：歌词为音乐内容。画面中的女主**不唱歌**——歌词承载的情绪由"说话/独白（感情词汇衬托）+ 琵琶琴声 + 配乐"表达（见 3.11），歌词本体由歌曲音轨（Master Audio）承担。
>
> ⚠️ v2.1.1 注：歌词同时仅为**灵感参考**——镜头从歌词提取意象与情绪后按剧情重新创作（非逐句对应，镜 13-15 已删史书/古城/王朝意象）。

---

# 第二部分：角色 Bible（最高优先级）

## 2.1 女主：琵琶女子（Pipa Woman）★ 全片唯一出镜角色

### 外貌固定系统

**脸**：鹅蛋脸，轮廓柔和，下颌线收细；三庭匀称，眉眼间距疏朗；杏眼，眼尾微挑，瞳孔深黑，目光含水含愁但不悲苦；远山黛眉，眉峰平缓，眉尾渐淡；鼻梁秀挺，鼻尖小巧；唇形饱满，唇色浅淡如花瓣；肤白如月，颧骨不高，清丽古典，无痣、无现代妆感。

**身体**：身高约 166cm，身形纤细，肩窄腰细，比例修长；端坐时脊背挺直，低头弹琴时脖颈线条优美，站姿轻盈；手指纤细修长，指节分明，拨弦动作干净有力（本片手部特写较多，此锚点最重要）。

**年龄（阶段变化规则）**：
- 阶段 A（22-24 岁，第一至五段）：高髻，眉目清亮，少女感略存
- 阶段 B（约 28-30 岁，第六段"多年后"）：**同一张脸**，发髻改低髻，眼角增加极细微的岁月感（仅用光线与神情表达，禁止皱纹堆砌），服装同款同色不变
- **规则：五官零变化，只允许发型与神态变化**；阶段 B 延伸（镜 13-15 时光无声段）：岁月仅以环境（四季流转）与神情（目光更深）表达，人脸五官零变化，禁止皱纹/白发/任何年龄化处理

### 角色固定 Prompt

**角色名称**：琵琶女子（Pipa Woman）
**固定身份**：盛唐浔阳江畔琵琶艺人，才艺出众，清冷温柔
**固定外貌**：鹅蛋脸，远山黛眉，含水杏眼，鼻梁秀挺，浅淡唇色；乌黑长发挽高髻（唐代宝髻式样），发间一支白玉簪；肤白如月；身高约 166cm，身形纤细，手指纤长
**固定服装（唐代规制）**：月白色交领齐胸襦裙（Tang-dynasty ruqun），衣身织金丝暗纹，外披浅青色轻纱披帛，腰系细带；全片唯一服装，禁止更换款式与颜色；**禁止清代服饰元素**
**固定气质**：清冷、温婉、孤独而不悲苦，目光如水

**AI 生成 Prompt（中文）**：
> 一位二十四岁的盛唐琵琶女子，鹅蛋脸，远山黛眉，杏眼含水含愁，鼻梁秀挺，唇色浅淡，乌黑长发挽唐代高髻，戴白玉簪，肤白如月，身形纤细，手指纤长，身穿月白色交领齐胸襦裙，衣身金丝暗纹，肩披浅青色轻纱披帛，怀抱白玉琵琶，气质清冷温婉，唐代妆容，电影摄影，真实人像。

**AI 生成 Prompt（英文锚点串 · L1 全局锚点，每个视频镜头必须原样嵌入）**：
> ANCHOR_PIPA_WOMAN: a 24-year-old classical Chinese woman of the Tang dynasty, oval face, sorrowful yet serene almond eyes, arched slender eyebrows, straight nose, soft pale lips, pale moon-like skin, black hair in an elegant Tang-style high bun secured with a white jade hairpin, wearing a moon-white Tang-dynasty ruqun dress with a cross collar and a high waistline, faint gold embroidery on the fabric, wide flowing sleeves, a pale cyan gauze scarf draped over her shoulders, slender figure, long delicate fingers, holding a white jade pipa, gentle melancholic presence, Tang dynasty makeup with slender painted eyebrows and subtle vermilion lips, live-action, photorealistic

## 2.2 男主：白衣故人（画外角色，全程不出镜）

> **v2.0 规则：男主不出现在任何画面中。**他是女子琴声、目光、回忆里的存在；他的"观看"由镜头（观众视角）代替。保留角色档案仅用于故事理解与镜头情绪参考。

**角色名称**：白衣故人（The Absent Scholar）
**固定身份**：远行的白衣书生，温润儒雅，与琵琶女子因琴声相识，后远行未归
**固定外貌（参考用，不出镜）**：身形颀长挺拔，白衣素绢宽袖长袍，腰束青色丝绦，手持素面折扇，温润如玉
**出镜规则**：
- 全片画面中**禁止**出现任何男性角色（含背影、剪影、手部）；
- 远景/全景中的"人群"与"舞者"为无个体特征的人群剪影（流动人群/女性舞者），同样禁止面部细节（3.9），与"男主不出镜"不冲突；
- 男主存在感通过三种方式传达：①女主目光方向（望向画外某处，镜头顺目光摇拍）；②女主说话/独白中提及（如"你"）；③剧情空镜（空船、空杯、江上另一艘船的空镜头）；
- 观众视角定义：镜头即男主眼睛——当她望向镜头方向，观众即被注视者；当她看镜头侧方远处，观众与她在同一"江上/灯下"空间。

---

# 第三部分：一致性系统（角色 + 场景 + 人脸距离 + 朝代 + 声音）

## 3.1 问题清单

| 问题 | 现象 | 风险 | 主要对策 |
|------|------|:---:|---------|
| 换脸 | 同角色不同镜头长相不同 | 高 | 三级锚点 + 批次顺序（3.2/3.3） |
| 换人 | 女子变另一女子 | 高 | L1 锚点全嵌 + 采样挑脸 |
| 年龄变化 | "多年后"生成成完全不同的脸 | 中 | 年龄变化规则入 prompt（2.1） |
| 衣服变化 | 月白裙变红/变纱裙/变清装 | 高 | 服装关键词库（3.6）+ 朝代锚定（3.10） |
| 发型变化 | 高髻变散发/变清式两把头 | 中 | L3 细节锁定 + 朝代锚定 |
| 场景漂移 | 同一场景光线/建筑/色调不同 | 高 | 场景锚点串 + 色板（3.7） |
| 远处人脸崩坏 | 全景/远景人脸糊成一团 | 高 | 人脸距离规则（3.9） |
| 朝代错误 | 唐代故事生成出清装/旗头/旗袍 | 高 | 朝代锚定规则（3.10） |

## 3.2 三级文字锚点制度（替代参考图锁定）

| 级别 | 内容 | 使用规则 |
|------|------|---------|
| **L1 全局锚点** | `ANCHOR_PIPA_WOMAN` 完整串 | 每个镜头必嵌，一字不改、禁止缩写 |
| **L2 镜头锚点** | 该镜头专属：表情编号（E1-E6）+ 动作编号（M1-M5）+ 服装固定词 | 从 3.5 摘取，与提示词库对应条目完全一致 |
| **L3 细节锁定** | 发型词、首饰词、手部特征词、朝代词 | 紧贴 L1 锚点同段出现，禁止变体 |

**执行铁律**：任何镜头 prompt 中，L1 锚点串与提示词库对应条目必须**逐字符相同**（复制粘贴，禁止重写）；锚点响应变差时先回退上一版本对比，再决定全片同步替换（禁止只改单个镜头）。

## 3.3 生成纪律

1. **设置统一**：全片同一模型（H3）、同一画幅（16:9 1920×1080）、同一运动强度档；中途不换模型。
2. **短镜头**：单条 3-5 秒，最长 5 秒——越长越容易漂移。
3. **批次顺序**（每批内连续完成）：
   - 第 1 批：女主特写/近景组（Shot 02、04、08、11、16、17）——同锚点串连打，让模型"记住"人脸；
   - 第 2 批：女主中景/全景组（Shot 05、06、10、12、13）；
   - 第 3 批：无人脸场景组（Shot 01、03、07、14、15、18）——03/07 含远景人群与舞者剪影，15 为背影禁人脸，一律无人脸细节。
4. **多采样挑脸**：每镜头采样 3-5 版，按"脸最像 → 服装一致 → 动作自然 → 光影"四关挑 1 版；相邻镜头截图拼图对比人脸。
5. **锚点镜头前置**：Shot 02 是全片第一张人脸，必须生成到"满意为止"再继续（后续镜头的人脸基准）。

## 3.4 观众视角原则（男主不出镜的镜头设计规则）

- 所有原"男主观看女主"的镜头，改为**镜头（观众）观看女主**：
  - Shot 04（初遇）：镜头从街心仰角缓缓上摇至楼上弹琴的女子——观众就是那个"在人群中驻足的人"，prompt 写 `the camera, as the audience's eye, looks up from the street toward her`；
  - Shot 05（江上双舫）：镜头位于另一艘"空船"上随行横移——女子在镜头侧前方弹琴，画面中无他人；
  - Shot 08（宫宴）：镜头位于席间观众席，女子独奏，镜头缓推；
  - Shot 09：女子独行回廊，镜头跟拍她离去，她渐行渐远不回头（"被目送"感）。
- 女主望向镜头方向的镜头仅限 2 个（Shot 04 回望、Shot 17 定格微笑），制造"她被注视"的对话感，其余望向画外远处。

## 3.5 表情库 / 动作库（L2 镜头锚点来源）

**表情库**：

| 编号 | 表情 | 文字锚点（英文） |
|------|------|-----------------|
| E1 | 专注弹琴 | eyes lowered to the strings, brows slightly knit in concentration |
| E2 | 望月思念 | lifting her gaze toward the moon, eyes soft with longing |
| E3 | 初见心动 | eyes widening slightly, a faint flush on her cheeks |
| E4 | 相知安宁 | a serene half-smile, eyes gentle and at ease |
| E5 | 悲恸垂泪 | a single tear sliding down her cheek, lips trembling |
| E6 | 多年沧桑 | the same face, gaze deeper and quieter, no tears |

**动作库**：

| 编号 | 动作 | 文字锚点（英文） |
|------|------|-----------------|
| M1 | 拨弦 | her slender fingers plucking the strings of the white jade pipa |
| M2 | 停弦 | her fingertips pausing above the vibrating strings |
| M3 | 举杯 | raising a small ceramic wine cup to her lips |
| M4 | 回眸 | turning her head slowly, glancing back over her shoulder |
| M5 | 拂袖 | her wide sleeve drifting in the night breeze |

## 3.6 服装关键词库（防服装漂移 + 防清装）

| 角色 | 固定词（禁止变体） | 禁止出现的变体 |
|------|------------------|--------------|
| 女主 | moon-white Tang-dynasty ruqun dress with cross collar and high waistline, faint gold embroidery, pale cyan gauze scarf | 红色、纱裙、露肩、现代裙、长披发、**旗袍/qipao、清式两把头、旗头、马褂** |
| 全片 | Tang-dynasty 朝代锚点词 | Qing dynasty, Manchu, qipao, cheongsam, mandarin collar, queue hairstyle, 官帽 |

## 3.7 场景一致性系统（场景锚点串 + 色板表）

**场景锚点串**（同一场景的所有镜头强制复用相同描述句，禁止改写）：

| 编号 | 场景 | 固定描述句（英文，复制使用） |
|------|------|------------------------------|
| SCENE_RIVER | 浔阳江夜 | misty autumn night on a Tang-dynasty river, full moon mirrored on dark ripples, a lone black awning boat with one dim lantern, reeds swaying on the bank |
| SCENE_MARKET | 长安夜市 | Tang-dynasty Chang'an night market, ten thousand red lanterns glowing like a river of stars, shop banners, crowded stone streets, incense smoke, wooden Tang buildings with upturned eaves |
| SCENE_TWOBOATS | 江上双舫 | two boats drifting side by side on the moonlit river, silver ripples breaking between them, one boat carrying a single warm lantern |
| SCENE_BANQUET | 大唐宫宴 | blazing Tang palace banquet hall, golden pillars, red curtains, hundreds of flickering palace lanterns, beaded curtains, Tang-style architecture |
| SCENE_RAINTOWER | 夜雨空楼 | rainy empty Tang-style tower at night, window half open with slanting rain drifting in, a single lamp burning on the table |
| SCENE_DUSKRIVER | 多年江岸 | grey-blue dusk over the Xunyang river, autumn leaves drifting, ink-wash mountains on the horizon |

**色板表**（写进每镜 prompt 末尾的 palette 词）：

| 段落 | 主色调 | 色板词（英文） |
|------|--------|---------------|
| 第 1 段 江夜 | 冷蓝银白 | cold blue-silver moonlight palette |
| 第 2 段 初遇 | 暖金 | warm golden lantern palette |
| 第 3 段 相知 | 银白+一点暖 | silver moonlight with a touch of warm lantern light |
| 第 4 段 盛世 | 金红 | gold-and-red candlelight palette |
| 第 5 段 离别 | 青灰 | cold blue-grey palette |
| 第 6 段 多年 | 青灰暮色 | grey-blue dusk palette |
| 第 7 段 时光无声 | 四季流转 | the four seasons turning over one riverside palette |
| 第 8 段 重逢 | 暖金流光 | warm golden bokeh palette |

**场景一致性铁律**：同场景镜头必须逐字复用场景锚点串 + 色板词；收口时统一 LUT + 35mm 颗粒抹平批差（见附 A）。

## 3.8 后期兜底方案（个别镜头仍漂移时）

- **方案 A（图生视频修复）**：从已通过镜头中挑"最像的一帧"，作为该漂移镜头图生视频的首帧，其余画面描述照抄提示词库原文。仅此一步引入图片，其余镜头仍为纯文字。
- **方案 B（换脸修复）**：ReActor / InsightFace 类工具，仅对漂移帧做局部 face swap 到锚点脸（需先导出 1 张锚点脸图）。全片最多允许使用 ≤ 3 个镜头。
- 使用兜底后，该镜头必须回到批次验收标准重新过四关。

## 3.9 人脸距离规则（远景可有人、禁人脸）★ v2.1 修订

> 模型在远距离描绘人脸时因像素占比过小会崩坏。v2.1 规则：**远景/全景允许出现人（身体、剪影、背影、局部），但禁止任何面部细节**——通过镜头限制只露身体或局部。

| 景别 | 人物占比 | 人脸策略 | 提示词写法 |
|------|---------|---------|-----------|
| 特写 | 面部占画幅 1/3 以上 | 可露脸，重点描写 | `her face clearly visible, sharp facial features` |
| 近景 | 肩部以上 | 可露脸 | `her face clearly visible` |
| 中景 | 腰部/膝部以上 | 可露脸，侧脸优先 | `her face visible, side profile favored` |
| 全景 | 人物高度 < 画面 1/3 | **可有人，禁止人脸** | `seen from behind / her face not visible / in silhouette, no facial detail` |
| 大远景 | 人物为小点 | **可有人（小点/剪影），禁止人脸** | `small figures, no individual facial detail` / `no close-ups of any face` |

**配套规则**：
1. 含人全景/大远景镜头（Shot 03 人群、05 背影、07 舞者剪影、09 背影、10 侧影、15 背影、16 人群剪影）：prompt 一律写明 `no facial detail` / `her face not visible` / `silhouettes`，远景人物只呈现身体、衣袂、剪影或背影；
2. 需要"远处人脸"叙事时（Shot 04 楼上女子），用仰角中景完成（保证人物占比），禁止用大远景交代人脸；
3. 人脸镜头统一批次前置生成（3.3 第 1 批）；
4. 验收：远景镜头出现任何清晰五官即判违规，重新生成。

## 3.10 朝代锚定规则（防清装）★ v2.0 新增

> 本片年代为**唐代（唐宋之际）**。生成视频出现清代元素（旗头、两把头、旗袍、马褂、清式建筑）时必须按本规则处理。

**正向锚定（写进每条 prompt）**：
- 朝代词：`Tang-dynasty era` 置于场景与环境词首；
- 服饰词（女主）：`Tang-dynasty ruqun dress with cross collar and high waistline`（齐胸襦裙）+ `wide flowing sleeves`；
- 发型词：`Tang-style high bun with a white jade hairpin`（唐代高髻/宝髻）；
- 妆容词：`Tang dynasty makeup, slender painted eyebrows, subtle vermilion lips`（禁止烟熏/现代妆）；
- 建筑词：`wooden Tang buildings with upturned eaves, tile roofs`；
- 器物词：`ceramic wine cups, bronze incense burners, silk banners, oil-paper lanterns`。

**负面词（加入第八部分，中英都要）**：
```text
Qing dynasty, Qing dynasty clothing, Manchu hairstyle, queue hairstyle, 清装, 旗头, 两把头, 旗袍, qipao, cheongsam, mandarin collar, 马褂, 马蹄袖, 清式建筑, 顶戴花翎, 剃发易服
```

**验收**：每镜头生成后人工检查发式（唐代高髻 vs 清式两把头）、领型（交领右衽 vs 立领盘扣）、袖型（宽袖 vs 马蹄袖）；违规即重生成。

## 3.11 声音与对白规则（说话不唱歌）★ v2.1 修订

> 试点反馈：人物唱歌效果差。v2.1 起女主**只说话/独白，禁止旋律性演唱**——台词为电视剧式的正常语言对话/独白，用感情词汇衬托（思念、不舍、释然等）。背景配乐由 `non_diegetic_music` 描述。

**女主出声机制**：
- **说话不唱歌**：所有出声镜头一律"说"而不是"唱"；prompt 内明写 `she speaks the line, not singing`，story_context 全局声明 `The woman never sings; she only speaks her lines with emotion like a TV drama actress`；
- 女主固定 speaker ID：`(S1)`，全片所有镜头保持一致；
- 台词交代方式（二选一，以提示词库为准）：
  - **`<d>` 硬台词**（v2.1.1 库当前采用，skill 标准）：`... a spoken line, not sung: <d>[Chinese] 你若在，这江月该有多好</d>`，中文原样保留不翻译；说话动词 + 感情词汇 + 口语化内容（**非歌词**）；
  - **散文式出声描述**（备用）：`the words she speaks are not a song but the thought she has carried all evening, spoken the way a person speaks to the moon` 等，配合感情词汇；
- 台词来源优先级：①口语独白（电视剧式，感情词汇衬托，**内容必须口语化、不能是歌词**）→ ②极短自语（每句 ≤ 10 字，含蓄不破故事）→ ③非语言人声（轻叹、泣声，写入 overall_soundscape）。

**本片台词分配表**（内容为"说话"语气，非唱）：

| 镜头 | 出声方式（说话不唱歌） | 内容/语气 |
|------|---------|---------------|
| Shot 02 | 轻声自语（思念） | `<d>` 硬台词："你若在，这江月该有多好"（口语化，非歌词） |
| Shot 04 | 琴声替代（不出声） | - |
| Shot 08 | 低声一句（席间自语） | `<d>` 硬台词："这一曲，我练了许多年"（口语化，非歌词） |
| Shot 10 | 短独白（饮后低语） | `<d>` 硬台词："酒还是温的，人却走远了"（口语化，非歌词） |
| Shot 11 | 泣声独白（声音发颤） | `<d>` 硬台词："你可知，我在等你"（口语化，非歌词，泣音） |
| Shot 12 | 释然自语（暮色独白） | `<d>` 硬台词："这么多年，还是只有这江水听我弹琴"（口语化，非歌词） |
| Shot 16 | 轻声一问（含希望） | `<d>` 硬台词："是你吗？"（口语化，非歌词） |
| Shot 17 | 低语（微笑定格） | `<d>` 硬台词："今生与你，若只如初遇"（口语化，非歌词） |
| 其余镜头 | 不出声（琴声为主） | - |

**背景配乐规则（non_diegetic_music）**：
- 每条 prompt 的 `non_diegetic_music` 字段完整描述该镜头对应歌曲段落的配乐：乐器（pipa/guqin/strings/drums）、速度、力度、动态变化，**禁止使用抽象情绪词**（如 sad music）；
- 全片配乐以《琵琶曲》原曲为 Master Audio，逐条视频的 non_diegetic_music 仅描述"该镜头窗口内"的配乐状态，剪辑时统一对齐原曲。

---

# 第四部分：素材资产库（纯文字清单）

> 纯文字版下，此清单用于：①核对分镜是否覆盖全部必需景别；②作为"图片版"升级时的一键生成清单。制作者逐项打勾。

## 4.1 人物素材（女主）

- [ ] 正面头像（E2 望月版）
- [ ] 半身照（弹琴姿态 M1）
- [ ] 全身照（江边站立）
- [ ] 左侧面（弹琴侧脸）
- [ ] 右侧面（回眸 M4）
- [ ] 背面（独坐船头背影）
- [ ] 坐姿（船头、楼阁窗前）
- [ ] 行走（江岸缓行）
- [ ] 特殊动作（举杯 M3、垂泪 E5、停弦 M2）
- [ ] 阶段 B 版（低髻、同脸、同服装）

## 4.2 场景素材（每场景 × 白天/夜晚/雨天/空镜）

| 场景 | 白天 | 夜晚 | 雨天 | 空镜 |
|------|:---:|:---:|:---:|:---:|
| 浔阳江岸+乌篷船 | - | 必做 | 可选 | 必做 |
| 长安夜市（万盏灯笼） | - | 必做 | - | - |
| 江面双舫（月夜） | - | 必做 | - | - |
| 大唐宫宴（胡旋舞） | 可选 | 必做 | - | - |
| 夜雨空楼 | - | 必做 | 必做 | 必做 |
| 江岸亭四季（时光无声段） | 必做 | - | 可选 | 必做 |
| 初见灯火街巷 | 可选 | 必做 | - | - |

---

# 第五部分：完整分镜设计（18 镜头 / 约 70 秒）

> 结构：8 段 × 2-3 镜头，单镜头 3-5 秒。切点对齐歌曲节拍（见附 A）。每镜字段：编号 / 时间 / 对应歌词 / 剧情目的 / 场景 / 人物动作 / 情绪 / 摄影机运动 / 景别 / 光影。**v2.1：全片无男性角色出镜；女主只说话不唱歌；远景可有人但禁人脸；每条 prompt 内嵌 story_context（片名/主题/承接落幅/贯穿意象）。** **v2.1.1：歌词为灵感参考（非逐句对应）；第七段改为「时光无声」（镜 13-15 人化时间）；镜 06 相知事件化（琴声相和）。**

## 第一段：江夜琴起（00:00-00:08）

### Shot 01
- **时间**：00:00-00:04（4 秒）
- **对应歌词**：前奏（琵琶独奏+古琴）
- **剧情目的**：建立故事世界与时代氛围
- **场景**：SCENE_RIVER 浔阳江夜，满月当空，江面薄雾，乌篷船停泊
- **人物动作**：无人物，琵琶声从画外起
- **情绪**：孤寂、静谧、期待
- **摄影机运动**：航拍缓缓下降（descending aerial）
- **景别**：大远景（无人物，不涉人脸规则）
- **光影**：月光铺满江面（冷蓝银白色板）

### Shot 02
- **时间**：00:04-00:08（4 秒）
- **对应歌词**：人间琴悠扬 / 姑娘把谁记心上
- **剧情目的**：引入女主，确立"琴"与"思念"两个意象（全片人脸基准镜头）
- **场景**：SCENE_RIVER 乌篷船头
- **人物动作**：女子端坐弹琴（E1+M1），轻声自语（S1，说话不唱歌），抬头望月（E2）
- **情绪**：清冷专注，眼底含思念
- **摄影机运动**：缓慢推近（slow push-in）
- **景别**：中景→近景（可露脸）
- **光影**：月光 + 船头一盏昏黄灯笼

## 第二段：初遇红尘（00:08-00:16）

### Shot 03
- **时间**：00:08-00:12（4 秒）
- **对应歌词**：南来与北往
- **剧情目的**：盛唐繁华的视觉冲击，为相遇铺垫
- **场景**：SCENE_MARKET 长安夜市
- **人物动作**：人群流动（无主角），女子身影隐约出现在楼上窗前
- **情绪**：繁华、躁动、热闹
- **摄影机运动**：航拍或大范围横移（aerial pan）
- **景别**：大远景（楼上人影为小点，prompt 注明 no facial detail）
- **光影**：暖金灯笼光（暖金色板）

### Shot 04
- **时间**：00:12-00:16（4 秒）
- **对应歌词**：美人取情寄琵琶 / 坐高楼赏小曲 抚琴声想起你（她坐高楼弹琴，观众街心听）
- **剧情目的**：第一次"对视"——观众视角的初见（男主不出镜，镜头即观众）
- **场景**：SCENE_MARKET 楼阁之上 + 街心仰望
- **人物动作**：女子凭栏弹琴，回眸望向镜头方向（M4，E3）；镜头（观众）自街心仰角上摇
- **情绪**：惊艳、初见心动
- **摄影机运动**：仰角缓慢上摇（tilt up）——`the camera, as the audience's eye, looks up from the street toward her`
- **景别**：中景（仰角，人物占比足，可露脸）
- **光影**：灯笼逆光 + 楼上暖光

## 第三段：琴音相知（00:16-00:24）

### Shot 05
- **时间**：00:16-00:20（4 秒）
- **对应歌词**：东船与西舫
- **剧情目的**：江上相望的静谧（镜头如另一艘空船随行）
- **场景**：SCENE_TWOBOATS 江面双舫
- **人物动作**：女子船尾弹琴（M1，E1）；镜头所在船空无一人
- **情绪**：静谧、温柔、默契
- **摄影机运动**：横移跟拍（tracking shot，位于相邻空船视角）
- **景别**：全景（女子为背影/侧影，人脸不可见——`seen from behind`）
- **光影**：月光银白 + 船灯一点暖色

### Shot 06
- **时间**：00:20-00:24（4 秒）
- **对应歌词**：琴音袅袅于心上
- **剧情目的**：以手部特写完成"琴声入心"的意象传递
- **场景**：SCENE_TWOBOATS 江面，月影摇碎
- **人物动作**：女子手指拨弦（M1 特写），衣袖微动（M5）
- **情绪**：相知安宁（E4）
- **摄影机运动**：极缓推近至手部（slow push-in）
- **景别**：特写（手部，不涉人脸规则）
- **光影**：月光勾勒手指轮廓，水面反光

## 第四段：盛世相伴（00:24-00:34）★ 视觉顶点

### Shot 07
- **时间**：00:24-00:28（4 秒）
- **对应歌词**：卿和了胡旋
- **剧情目的**：盛唐宫宴的华美
- **场景**：SCENE_BANQUET 宫宴大殿
- **人物动作**：胡旋舞者旋转长袖翻飞（群舞，无人脸特写），宾客觥筹交错
- **情绪**：极盛、欢腾
- **摄影机运动**：环绕大殿（arc shot）
- **景别**：全景（群舞，无个人人脸）
- **光影**：数百盏宫灯，金红主调（金红色板）

### Shot 08
- **时间**：00:28-00:31（3 秒）
- **对应歌词**：君作汉宫琵琶语 / 半掩面惆怅（珠帘半掩）
- **剧情目的**：盛世中女子的独奏——观众在席间看她
- **场景**：SCENE_BANQUET 席间，珠帘半垂
- **人物动作**：女子侧身奏琴（E1），低声一句（S1，说话不唱歌）；镜头位于席间观众席，缓推
- **情绪**：美好、安宁、满足（E4）
- **摄影机运动**：缓慢推近（slow push-in）
- **景别**：中景（双人→单人：女主独奏）
- **光影**：烛光暖调，珠帘光斑

### Shot 09
- **时间**：00:31-00:34（3 秒）
- **对应歌词**：（间奏，衔接句）
- **剧情目的**：极盛之下的独行，为骤落蓄势（"被目送"感）
- **场景**：宫宴回廊，灯火阑珊处
- **人物动作**：女子独行回廊（背影），衣袖微拂，渐行渐远不回头
- **情绪**：温柔、珍惜、渐远
- **摄影机运动**：跟拍背影（tracking，从后）
- **景别**：全景（背影，`seen from behind, her face not visible`）
- **光影**：回廊灯笼，逆光剪影

## 第五段：离别悲歌（00:34-00:42）★ 情绪顶点

### Shot 10
- **时间**：00:34-00:37（3 秒）
- **对应歌词**：姑娘不胜酒力 / 坐高楼赏烟雨 烟雨声宛如你（雨声如故人）
- **剧情目的**：情绪骤落——从宫宴极盛切到雨夜空楼
- **场景**：SCENE_RAINTOWER 夜雨空楼
- **人物动作**：女子独坐举杯（M3），饮尽后垂首低语（S1）；桌边另一只酒杯无人碰过
- **情绪**：悲恸将至、强撑
- **摄影机运动**：缓慢拉远（slow pull-out）
- **景别**：全景（女子背影侧影，`her face turned away`）
- **光影**：孤灯一盏，冷雨反光（青灰色板）

### Shot 11
- **时间**：00:37-00:42（5 秒）
- **对应歌词**：恨只恨泪两行 / 哭的梨花带雨（以单泪落弦凝练呈现）
- **剧情目的**：全片情绪最高潮——泪落琴弦，琴音顿止
- **场景**：SCENE_RAINTOWER 案前，琵琶横置
- **人物动作**：一滴泪滑落（E5），落在琴弦上；指尖停在弦上（M2），泣声一句（S1），琴音止
- **情绪**：极度悲恸、无声
- **摄影机运动**：极缓推近至泪滴（slow push-in）
- **景别**：特写（泪+弦，脸颊半入画）
- **光影**：孤灯微光，泪珠反光，周围渐暗

## 第六段：故人已远（00:42-00:50）

### Shot 12
- **时间**：00:42-00:46（4 秒）
- **对应歌词**：美人迟了暮 / 弹一首琵琶曲 叹离愁争朝夕
- **剧情目的**：多年后的女子，同一把琴，同一处江岸
- **场景**：SCENE_DUSKRIVER 江岸亭中
- **人物动作**：女子（阶段 B：同脸、低髻、目光更深 E6）再次拨弦（M1），释然自语（S1，说话不唱歌）
- **情绪**：苍凉、释然
- **摄影机运动**：横移缓慢经过（slow lateral move）
- **景别**：中景（可露脸，侧脸优先）
- **光影**：暮色青灰（青灰暮色板）

### Shot 13
- **时间**：00:46-00:50（4 秒）
- **对应歌词**：思念一夜未停 / 叹离愁争朝夕（灵感）
- **剧情目的**：以四季流转写「时光无声」——岁月环绕她、却不改变她（露脸，同脸零变化）
- **场景**：SCENE_DUSKRIVER 同一江岸亭、同一石凳
- **人物动作**：女子（阶段 B：同脸、低髻、目光更深 E6）坐亭中弹同一曲，四季叠化流转（春樱→夏荷→秋苇→冬雪），披帛微褪；落幅雪落琴弦
- **情绪**：怅惘、流逝感
- **摄影机运动**：固定机位极缓推近（fixed slow push-in）
- **景别**：中景（可露脸，侧脸优先）
- **光影**：四季各自光色，暮色青灰为底（四季流转色板）

## 第七段：时光无声（00:50-00:58）

### Shot 14
- **时间**：00:50-00:54（4 秒）
- **对应歌词**：思念一夜未停（灵感：雪融成泪，呼应"哭的梨花带雨"）
- **剧情目的**：手与琴上的岁月——琴身包浆、雪融如泪（呼应镜 11 泪落琴弦）
- **场景**：SCENE_DUSKRIVER 亭内同石凳（同一把白玉琵琶）
- **人物动作**：特写纤手停弦；雪融成滴挂弦如泪；指尖轻抚琴身；抬眸望江（E2 目光，眼不入画）
- **情绪**：释然、岁月静默
- **摄影机运动**：固定机位极缓推近（fixed slow push-in）
- **景别**：手部特写（眼不入画，可及下颌）
- **光影**：暮色青灰，雪与玉的微光（四季流转色板）

### Shot 15
- **时间**：00:54-00:58（4 秒）
- **对应歌词**：回首人间（灵感：放下与离开）
- **剧情目的**：告别——放琴、望江、走入暮色；空亭余琴与纱巾（时间的「放下」）
- **场景**：SCENE_DUSKRIVER 亭外江岸
- **人物动作**：女子背影放琴于石凳（M4），望江一眼，转身走入暮色；空亭余白玉琵琶与浅青纱巾一角，风过纱巾落（全程背影，禁人脸）
- **情绪**：释然、孤独
- **摄影机运动**：全景起，缓拉至大远景（slow pull-out）
- **景别**：全景→大远景（背影，`her face not visible`）
- **光影**：暮色青灰，落幅一线暮光（衔接镜 16 暖金）

## 第八段：初遇终章（00:58-01:06）

### Shot 16
- **时间**：00:58-01:02（4 秒）
- **对应歌词**：回首人间 笑谈你我初遇 / 今生与你
- **剧情目的**：时间倒转，回到第一次相遇
- **场景**：SCENE_MARKET 初见灯火街巷
- **人物动作**：女子立于灯火之下，听见身后呼唤，缓缓转身（M4），轻声一问（S1）
- **情绪**：心动重现、命运感
- **摄影机运动**：环绕半圈（arc shot）
- **景别**：中景（可露脸）
- **光影**：暖金灯笼光，微微失焦的流光（暖金流光色板）

### Shot 17
- **时间**：01:02-01:05（3 秒）
- **对应歌词**：若只如初遇
- **剧情目的**：最终情感落点——美好定格
- **场景**：SCENE_MARKET 灯火光晕
- **人物动作**：女子回眸微笑（E3 重现），望向镜头方向，低语（S1），时间停住（画面近乎静止，仅发丝微动）
- **情绪**：释然、永恒之美
- **摄影机运动**：静帧感（极缓推近 1mm）
- **景别**：特写（面部 45°）
- **光影**：暖光柔化，光晕包裹

### Shot 18
- **时间**：01:05-01:10（5 秒）
- **对应歌词**：（尾奏）字幕：今生与你，若只如初遇
- **剧情目的**：收束——月光、琴声、消散
- **场景**：SCENE_RIVER 浔阳江夜，乌篷船远去
- **人物动作**：无人物；琴声渐散
- **情绪**：余韵、安然
- **摄影机运动**：缓慢拉远（slow pull-out）至定格
- **景别**：大远景（无人物）
- **光影**：月光渐淡，黑场淡出

---

# 第六部分：AI 图片 Prompt（每镜头，图片版预留资产）

> 本手册为 T2VA 纯文字版，此部分不参与本次制作；保留用于日后"图片版"升级（I2VA/FL2VA 需首帧图）与 3.8 后期兜底。格式：[主体][环境][动作][电影摄影][质量参数]，中英各一。

### Shot 01
**中**：深秋浔阳江夜景，满月倒映江面，薄雾弥漫，乌篷船停泊，船头昏黄灯笼；[环境] 唐代江岸，远山朦胧，芦苇轻摇；[动作] 江水缓缓流动，雾气飘移；[摄影] 航拍大远景，35mm 胶片，冷蓝银白月光，浅景深；[质量] 4K 电影质感，东方古典美学。
**EN**：Autumn night on the Xunyang River, full moon mirrored on misty water, a lone black awning boat with a dim lantern；[environment] Tang-dynasty riverbank, hazy hills, swaying reeds；[action] slow current, drifting mist；[cinematography] aerial extreme wide, 35mm film, cold silver-blue moonlight, shallow DOF；[quality] 4K cinematic realism, oriental aesthetics.

### Shot 02
**中**：二十四岁盛唐琵琶女子端坐船头，鹅蛋脸，远山黛眉，杏眼含水，乌发唐代高髻白玉簪，月白交领齐胸襦裙金丝暗纹，浅青披帛，怀抱白玉琵琶；[环境] 浔阳江夜，满月，船头灯笼；[动作] 手指拨弦，抬头望月；[摄影] 中景推近，35mm 胶片，月光+灯笼光，浅景深；[质量] 4K 真实人像，唐代妆容，真实皮肤质感。
**EN**：A 24-year-old Tang pipa woman on a boat bow, oval face, sorrowful almond eyes, Tang-style high bun with jade hairpin, moon-white Tang ruqun with gold embroidery and pale cyan scarf, holding a white jade pipa；[environment] Xunyang river at night, full moon, dim lantern；[action] plucking strings, gazing at the moon；[cinematography] medium shot, 35mm film, moonlight and lantern light, shallow DOF；[quality] 4K photorealistic, Tang dynasty makeup.

### Shot 03
**中**：大唐长安夜市全景，万盏红灯笼如星河，旗幡招展，人流如织；[环境] 唐代都城街巷，飞檐楼阁，酒旗茶肆；[动作] 人群流动，灯火摇曳；[摄影] 航拍大远景，暖金灯笼光，35mm 胶片；[质量] 4K 电影质感，盛世繁华。
**EN**：Tang Chang'an night market, ten thousand red lanterns like a river of stars, banners, crowded streets；[environment] Tang streets, flying eaves, taverns；[action] moving crowd, flickering lanterns；[cinematography] aerial extreme wide, warm golden lantern light, 35mm film；[quality] 4K cinematic.

### Shot 04
**中**：长安夜市楼阁之上，琵琶女子凭栏弹琴回眸望向镜头下方，眉眼含光；[环境] 唐代木构楼阁，飞檐，暖金灯笼，逆光；[动作] 回眸、指尖停弦；[摄影] 中景仰角（镜头自街心仰望），暖光逆剪+楼上柔光，35mm 胶片；[质量] 4K 真实人像，电影感。
**EN**：The pipa woman at the upstairs window of a Tang tower, playing and glancing back toward the camera below, eyes catching the light；[environment] wooden Tang tower, upturned eaves, golden lanterns, backlight；[action] glancing back, fingers pausing on strings；[cinematography] medium low-angle shot (audience's eye from the street), warm rim light, 35mm film；[quality] 4K photorealistic.

### Shot 05
**中**：浔阳江面两艘船并行，月光倒映；一艘船上琵琶女子弹琴（背影/侧影），另一艘空船船头一盏灯笼；[环境] 唐代江面，薄雾远山；[动作] 两船并行，水波荡漾；[摄影] 全景横移跟拍，月光银白+船灯暖点，35mm 胶片；[质量] 4K 电影质感，静谧东方美学。
**EN**：Two boats drifting side by side on the moonlit Xunyang river; the pipa woman playing on one (seen from behind), the other boat empty with a single lantern；[environment] Tang river, mist, distant hills；[action] boats advancing, ripples；[cinematography] wide tracking, silver moonlight with warm lantern accent, 35mm film；[quality] 4K cinematic.

### Shot 06
**中**：特写：纤细修长的女子手指轻拨琵琶琴弦，指尖落弦，月影在水面摇碎；[环境] 江面夜色，月光反光；[动作] 拨弦，涟漪；[摄影] 手部特写，极浅景深，月光勾勒手指，35mm 胶片；[质量] 4K 电影质感，真实皮肤与琴弦细节。
**EN**：Close-up of slender feminine fingers plucking pipa strings, broken moonlight shimmering on water behind；[environment] river night, moon reflections；[action] plucking, ripples；[cinematography] hand close-up, ultra-shallow DOF, moonlit finger contours, 35mm film；[quality] 4K cinematic, real detail.

### Shot 07
**中**：大唐宫宴大殿全景，灯火辉煌，胡旋舞女旋转长袖翻飞，宾客如云；[环境] 盛唐宫殿，金柱红帐，数百盏宫灯；[动作] 胡旋旋转，衣袂飘飞；[摄影] 全景环绕感，金红暖调，烛光，35mm 胶片；[质量] 4K 电影质感，盛世华美。
**EN**：Grand Tang palace banquet hall, blazing lanterns, whirling Hu-xuan dancers with flying sleeves；[environment] Tang palace, golden pillars, red curtains, hundreds of lanterns；[action] dancers spinning, sleeves flying；[cinematography] wide arc feel, gold-and-red candlelight, 35mm film；[quality] 4K cinematic.

### Shot 08
**中**：宫宴席间珠帘半垂，琵琶女子侧身独奏，低眉专注，烛光映面；[环境] 盛唐宫宴，烛光，珠帘光斑；[动作] 拨弦，低语；[摄影] 中景，烛光暖调，浅景深，35mm 胶片；[质量] 4K 真实人像。
**EN**：At a Tang banquet, beaded curtain half-drawn, the pipa woman playing alone, eyes lowered in concentration, candlelight on her face；[environment] palace banquet, candlelight, bead-curtain bokeh；[action] plucking strings；[cinematography] medium shot, warm candlelight, shallow DOF, 35mm film；[quality] 4K photorealistic.

### Shot 09
**中**：宫宴回廊，灯火阑珊，琵琶女子独行（背影），衣袖轻拂，渐行渐远；[环境] 唐代宫殿回廊，灯笼渐稀，夜色将深；[动作] 缓行，衣袖飘动；[摄影] 全景背影跟拍，逆光剪影，35mm 胶片；[质量] 4K 电影质感，含蓄东方美学。
**EN**：Palace corridor at dusk, lanterns thinning, the pipa woman walking away alone (from behind), sleeves drifting, never turning back；[environment] Tang palace corridor, dimming lanterns；[action] slow walking, sleeves moving；[cinematography] wide back-view tracking, backlit silhouette, 35mm film；[quality] 4K cinematic.

### Shot 10
**中**：夜雨空楼，窗棂半开，雨丝斜入，女子独坐举杯，案上两只酒杯一只未动；[环境] 唐代楼阁，青灰雨夜，孤灯一盏；[动作] 举杯饮尽，垂首；[摄影] 全景慢拉，冷雨反光，青灰调，35mm 胶片；[质量] 4K 电影质感，悲凉意境。
**EN**：Rainy empty Tang tower, window half open, slanting rain, the woman alone raising a cup, two cups on the table one untouched；[environment] grey-blue rainy night, a single lamp；[action] drinking, lowering her head；[cinematography] wide slow pull-out, cold rain reflections, blue-grey palette, 35mm film；[quality] 4K cinematic.

### Shot 11
**中**：特写：一滴泪滑落女子脸颊，落在琵琶琴弦上，指尖停驻弦上；[环境] 空楼案前，孤灯微光，周围渐暗；[动作] 泪落触弦，指尖停驻；[摄影] 特写，泪珠反光，极浅景深，35mm 胶片；[质量] 4K 电影质感，真实眼泪与皮肤细节。
**EN**：Close-up of a single tear sliding down her cheek onto the pipa string, fingertips frozen above the strings；[environment] empty tower, dim lamp, darkening edges；[action] tear falling onto string, fingers pausing；[cinematography] extreme close-up, tear glinting, ultra-shallow DOF, 35mm film；[quality] 4K cinematic, real detail.

### Shot 12
**中**：多年后江岸亭中，同一位琵琶女子（同脸，低髻，目光更深）再次拨弦；[环境] 秋意更浓的浔阳江岸，暮色青灰；[动作] 指尖落弦，衣袖微动；[摄影] 中景横移，暮光反光，35mm 胶片；[质量] 4K 电影质感，岁月苍凉。
**EN**：Years later, the same pipa woman (same face, lower bun, deeper gaze) playing again in a riverside pavilion；[environment] more autumnal riverbank, grey-blue dusk；[action] fingers landing on strings；[cinematography] medium lateral move, dusk light, 35mm film；[quality] 4K cinematic, weathered mood.

### Shot 13
**中**：同一江岸亭中，琵琶女子坐石凳弹琴，四季在身侧叠化流转（春樱→夏荷→秋苇→冬雪），暮色青灰为底；[环境] 唐代江岸亭，四季光色；[动作] 四季流转，指尖拨弦；[摄影] 中景固定机位极缓推近，叠化转场，35mm 胶片；[质量] 4K 电影质感，时光无声。
**EN**：The same riverside pavilion, the pipa woman on the stone bench playing the same tune, the four seasons dissolving around her (cherry blossom, lotus, golden reeds, snow)；[environment] Tang riverside pavilion, seasonal light；[action] seasons turning, fingers plucking；[cinematography] medium fixed slow push-in, dissolves, 35mm film；[quality] 4K cinematic, time passing silently.

### Shot 14
**中**：手部特写：纤手停弦，雪融成滴挂弦如泪，指尖轻抚白玉琴身；[环境] 江岸亭内，暮色青灰，雪落亭外；[动作] 停弦、轻抚琴身、抬眸望江；[摄影] 特写固定机位极缓推近，35mm 胶片；[质量] 4K 电影质感，岁月在指间。
**EN**：Hand close-up: slender fingers stilling on the strings, a melted snowflake hanging like a tear, fingers tracing the jade body；[environment] pavilion at grey-blue dusk, snow beyond the rail；[action] stilling, caressing, lifting the gaze；[cinematography] extreme close-up fixed slow push-in, 35mm film；[quality] 4K cinematic, years on the hands.

### Shot 15
**中**：女子背影放琴于石凳，望江一眼，走入暮色；空亭余白玉琵琶与浅青纱巾，风过纱巾落；[环境] 江岸亭外，暮色青灰，一线暮光；[动作] 放琴、望江、离去；[摄影] 全景缓拉至大远景，35mm 胶片；[质量] 4K 电影质感，告别与空亭。
**EN**：The woman from behind setting the pipa down on the bench, a last look at the river, walking into the dusk; the empty pavilion keeping the pipa and the pale cyan scarf；[environment] riverbank pavilion at deep dusk, a last line of warm light；[action] setting down, looking, leaving；[cinematography] full shot slow pull to extreme wide, 35mm film；[quality] 4K cinematic, farewell.

### Shot 16
**中**：初见的长安灯火街巷，琵琶女子立于灯火之下，缓缓转身回眸；[环境] 长安夜市，暖金灯笼光，微微失焦流光；[动作] 转身、回眸；[摄影] 中景环绕半圈，暖光，35mm 胶片；[质量] 4K 电影质感，命运重逢感。
**EN**：The same Chang'an lantern street of their first meeting; the pipa woman under the lights slowly turning to look back；[environment] night market, warm golden lantern glow, soft bokeh；[action] turning, glancing back；[cinematography] medium half-arc, warm light, 35mm film；[quality] 4K cinematic.

### Shot 17
**中**：特写：女子回眸微笑，灯火光晕包裹面容，发丝微动，时间停住；[环境] 灯笼光晕，暖金流光；[动作] 回眸微笑定格，仅发丝微动；[摄影] 面部 45° 特写，极浅景深，静帧感，35mm 胶片；[质量] 4K 电影质感，永恒之美。
**EN**：Close-up of the woman's smiling glance back, face wrapped in lantern glow, a few strands of hair moving, time frozen；[environment] warm lantern bokeh；[action] frozen smile, only hair drifting；[cinematography] 45° face close-up, ultra-shallow DOF, still-frame feel, 35mm film；[quality] 4K cinematic.

### Shot 18
**中**：浔阳江夜，乌篷船缓缓远去，月影在水面散开，雾气渐起；[环境] 唐代江岸夜景，满月；[动作] 船远去，月影散开；[摄影] 大远景缓慢拉远，月光渐淡，35mm 胶片；[质量] 4K 电影质感，余韵悠长。
**EN**：Night on the Xunyang river, the awning boat drifting away, the moon's reflection dissolving on the water, mist rising；[environment] Tang river night, full moon；[action] boat receding, reflections dissolving；[cinematography] extreme wide slow pull-out, fading moonlight, 35mm film；[quality] 4K cinematic.

---

# 第七部分：AI 视频 Prompt（T2VA 纯文字 · MiniMax H3 官方结构）

> **完整 18 条视频提示词见同目录《琵琶曲_视频提示词库.md》**（每条 6000-7000 字符，H3 单条上限 7000）；已导出 18 个 TXT 至 `prompt/txt/`（`Shot_XX_短名.txt`，每镜一个，直接复制上传）。本部分为使用规范与检索表。

## 7.1 编写依据与格式

依据 MiniMax H3 `h3-prompt-writing` 官方 Skill（T2VA 模式）与 `music-video-subtitle-generator`（MV 多镜头拼接）。每条 prompt 以 **story_context**（全局主题注入，v2.1 新增）开头，后接三段式字段：

```
story_context: 片名《琵琶曲》/ 主题"若只如初遇" / Shot N of 18 / 上下镜承接与落幅 / 贯穿意象（满月、乌篷船、红灯笼、月白裙青纱、白玉琵琶）/ 时空层（江夜冷蓝当下 vs 长安暖金回忆）/ 说话不唱歌声明
integrated_multimodal_description: 沿时间轴描述视觉、动作、镜头、切点、说话/独白（speaker ID，说话不唱歌）
overall_soundscape: 1-4 句英文总结环境声 + 动作声 + 非语言人声（说话/独白不重复写入）
non_diegetic_music: 1-3 句英文描述该镜头窗口内的配乐（乐器/速度/力度/动态，禁抽象情绪词）
```

## 7.2 每条 prompt 的必含要素（生成前逐项自查）

1. **story_context**（v2.1 必含）：片名/主题/`Shot N of 18`/上下镜承接与落幅/贯穿意象/时空层/说话不唱歌声明（见库内每条开头）
2. **L1 锚点串**：`ANCHOR_PIPA_WOMAN` 完整嵌入（阶段 B 镜头换阶段 B 变体，见库内 Shot 12）
3. **场景锚点串**：按 3.7 表逐字复制对应 SCENE_ 句
4. **色板词**：按段落表（3.7）写入 prompt 末尾
5. **人脸距离规则**：按 3.9 表写入 `her face clearly visible` 或 `seen from behind / no facial detail` 等（远景可有人禁人脸）
6. **朝代词**：`Tang-dynasty era` 置于场景词首（3.10）
7. **镜头运动**：类型 + 幅度 + 速度 三维自然语言（如 `The camera pushes in with small amplitude at slow speed`）
8. **说话/独白**：按 3.11 台词分配表，散文式出声描述（`she speaks the line, not singing`）或 `(S1)` + `<d>[Chinese] …</d>`；**禁止唱歌指令**
9. **Negative Prompt**：第八部分统一负面词追加在每条末尾
10. **字符量**：6000-7000 字符（不含 Negative Prompt）；不足时补充环境细节/动作分拍/光影描写

## 7.3 镜头检索表（提示词库索引）

| Shot | 时间 | 场景 | 人脸策略 | 出声 |
|------|------|------|---------|------|
| 01 | 00:00-00:04 | SCENE_RIVER | 无人 | 琴声起 |
| 02 | 00:04-00:08 | SCENE_RIVER | 露脸（基准） | 自语（说话不唱歌） |
| 03 | 00:08-00:12 | SCENE_MARKET | 人群剪影禁人脸 | 无 |
| 04 | 00:12-00:16 | SCENE_MARKET | 露脸（仰角） | 琴声 |
| 05 | 00:16-00:20 | SCENE_TWOBOATS | 背影 | 无 |
| 06 | 00:20-00:24 | SCENE_TWOBOATS | 手部特写 | 无 |
| 07 | 00:24-00:28 | SCENE_BANQUET | 舞者剪影禁人脸 | 无 |
| 08 | 00:28-00:31 | SCENE_BANQUET | 露脸 | 说话（低语一句） |
| 09 | 00:31-00:34 | 回廊 | 背影 | 无 |
| 10 | 00:34-00:37 | SCENE_RAINTOWER | 侧影/低头 | 独白（饮后低语） |
| 11 | 00:37-00:42 | SCENE_RAINTOWER | 特写半脸 | 泣声独白 |
| 12 | 00:42-00:46 | SCENE_DUSKRIVER | 露脸（阶段 B） | 自语（说话不唱歌） |
| 13 | 00:46-00:50 | SCENE_DUSKRIVER | 露脸（阶段 B） | 无 |
| 14 | 00:50-00:54 | SCENE_DUSKRIVER | 手部特写 | 无 |
| 15 | 00:54-00:58 | SCENE_DUSKRIVER | 背影禁人脸 | 无 |
| 16 | 00:58-01:02 | SCENE_MARKET | 露脸 | 轻问（说话不唱歌） |
| 17 | 01:02-01:05 | SCENE_MARKET | 露脸（特写） | 低语（说话不唱歌） |
| 18 | 01:05-01:10 | SCENE_RIVER | 无人 | 琴声散 |

---

# 第八部分：Negative Prompt（全片统一负面词）

> 每条视频与图片 prompt 末尾必须追加。英文为主（生成模型对英文负面词响应最好），中文供可灵等中文模型使用。

**英文（统一追加）：**
```text
different face, different person, wrong identity, face changing, age change, cartoon, anime, illustration, anime style, bad anatomy, extra fingers, deformed hands, mutated hands, plastic skin, porcelain skin, glossy skin, modern clothes, modern buildings, modern objects, cars, electric lights, neon signs, jeans, sneakers, watermark, text artifacts, blurry, low quality, Qing dynasty, Qing dynasty clothing, Manchu hairstyle, queue hairstyle, qipao, cheongsam, mandarin collar
```

**中文（可灵等中文模型）：**
```text
不同面孔，人物换脸，身份错误，卡通，动漫，插画，五官畸形，多余手指，手部变形，塑料皮肤，过度磨皮，现代服装，现代建筑，现代物品，车流，霓虹灯，水印，文字乱码，模糊，低画质，清装，清式服装，旗头，两把头，旗袍，马褂，马蹄袖，剃发易服
```

**分类说明（对应 MIX 规范）：**

| 类别 | 关键负面词 |
|------|----------|
| 人物 | different face, different person, wrong identity, face changing, age change |
| 画面 | cartoon, anime, illustration, anime style |
| 身体 | bad anatomy, extra fingers, deformed hands, mutated hands |
| 皮肤 | plastic skin, porcelain skin, glossy skin |
| 时代 | modern clothes, modern buildings, modern objects, cars, electric lights, neon signs |
| 朝代 | Qing dynasty, Qing dynasty clothing, Manchu hairstyle, queue hairstyle, qipao, cheongsam, mandarin collar（中文：清装/旗头/两把头/旗袍/马褂） |
| 质量 | watermark, text artifacts, blurry, low quality |

---

# 第九部分：AI 突发问题处理方案（故障排查）

## 问题 1：人物不像（锚点串未生效）
- **排查**：检查该镜头 prompt 是否原样嵌入 `ANCHOR_PIPA_WOMAN`（有无改写、缩写、形容词被删）；与提示词库对应条目逐字符比对。
- **解决**：① 恢复完整 L1 锚点串，置于 `[Shot 1]` 风格声明之后、动作之前；② 降低动作复杂度（先静态 `she remains seated` 再加 `plucks`）；③ 仍不像 → 重写锚点串一次并**全片同步替换**（禁止只改单个镜头）；④ 同一 prompt 采样 3-5 次选最佳。

## 问题 2：视频人物换脸
- **解决**：① 确认镜头时长 ≤ 5 秒；② 减少特写，改中景/全景；③ 女主露脸镜头限制在正脸 45° 内，禁止大角度转头；④ 仍漂移 → 走 3.8 后期兜底（图生视频首帧修复 / ReActor 换脸）。

## 问题 3：服装变化（月白裙变色/变款/变清装）
- **解决**：① 强制使用服装关键词库（3.6），禁止任何变体词；② 服装词紧贴锚点串放置：`moon-white Tang-dynasty ruqun dress with cross collar and high waistline, faint gold embroidery, pale cyan gauze scarf`；③ 检查 Negative Prompt 是否含 `qipao` 等冲突项；④ 生成后相邻镜头服装截图逐帧比对。

## 问题 4：手部错误（弹琴特写多，风险高）
- **解决**：① 手部特写镜头控制数量（本片仅 Shot 06 一个纯手部特写，Shot 11 手指藏于琴颈阴影中）；② 手部半入画/被衣袖遮挡部分；③ 多次采样挑最干净一版；④ 若模型支持局部重绘，仅对坏手帧修复。

## 问题 5：动作僵硬
- **解决**：① 动作描写用自然语言带节奏：`her hand moves in a slow, natural arc`，不堆关键词；② 单镜头保持"一个主动作 + 一个微动作"（如拨弦 + 抬眼），不超过三个动作；③ 镜头运动放慢：`with small amplitude at slow speed`；④ 长镜头切成 2-4 秒短镜头拼接（见附 A）。

## 问题 6：古代环境现代化
- **解决**：① 确保 Negative Prompt 含 `modern buildings, modern objects, electric lights, neon signs`；② 环境词首固定朝代锚点 `Tang-dynasty era`；③ 街市场景限定 `wooden Tang buildings with upturned eaves, no glass windows, no plastic, no signage`；④ 出图后人工排查灯笼/旗幡/建筑样式，违反即重生成。

## 问题 7（本片特有）：第六段"多年后"被生成成另一个女人
- **解决**：① 年龄变化规则写入 prompt：`the same face, hair in a lower bun, gaze deeper, no wrinkles`；② 服装同款同色是"同一个人"的最强信号，必须保持；③ 先做批次 1（2/4/8/11/16/17 号）锚定人脸，再做批次 2 的 12/13 号（阶段 B，同脸低髻）；④ 与女主其他镜头截图对比验收。

## 问题 8（本片特有）：同场景光线/建筑不统一
- **解决**：① 同场景镜头逐字复用场景锚点串（3.7），禁止改写；② 色板词必须与段落对应；③ 收口统一 LUT + 35mm 颗粒（附 A.5）；④ 若个别镜头色差过大，仅重做该镜头（用同场景锚点串原样重生成）。

## 问题 9（v2.0 新增）：远处人脸崩坏（糊脸/五官错乱）
- **解决**：① 确认是否违反 3.9 人脸距离规则——全景/大远景带人脸即违规，改为 `seen from behind / her face turned away / in silhouette` 重生成；② 必须远处露脸时，改用仰角中景（拉近人物占比）；③ 若特写/近景也崩坏，检查 Negative 是否误伤（如 face 相关词），并降低动作复杂度。

## 问题 10（v2.0 新增）：生成出清装/旗头/旗袍
- **解决**：① 确认朝代词 `Tang-dynasty era` 在场景词首；② 发型写 `Tang-style high bun with a white jade hairpin`（禁"两把头"类描述）；③ 服装写 `Tang-dynasty ruqun dress with cross collar`；④ Negative Prompt 必须含 Qing/旗头/旗袍/马褂；⑤ 违规镜头直接重生成，不手工修补。

## 问题 11（v2.1 修订）：人物出声变成"唱歌" / 口型与台词不符 / 没有出声
- **解决**：① 唱歌 → 确认 prompt 内明写 `she speaks the line, not singing` 且 story_context 含 `The woman never sings; she only speaks her lines with emotion like a TV drama actress`；台词一律按 3.11 用说话语气，**内容必须是口语化独白（非歌词），并写入 `<d>[Chinese] …</d>` 硬台词**——只有散文式描述、或台词内容是歌词时，模型仍会倾向演唱；② 口型对不上 → 减小台词长度（≤ 10 字），或改画外独白（镜头拍背影/侧影，声画分离更自然）；③ 独白镜头优先选侧脸/背面景别（3.9 允许），降低口型要求；④ 仍无声 → 检查出声描述是否在 `integrated_multimodal_description` 内（不含则补），或改用 `<d>[Chinese] …</d>` 硬台词；⑤ 仍无声 → 剪辑阶段从 Master Audio 补人声（本片为 MV，主歌即全局音轨，见附 A）。

---

# 第十部分：不同 AI 工具适配

## 10.1 工具分工

| 工具 | 本片适合环节 | 说明 |
|------|------------|------|
| **MiniMax H3（海螺）** | 全片 18 条视频生成（主力） | T2VA 纯文字模式与本手册完全匹配；单条 3-5 秒，prompt 6000-7000 字符 |
| 可灵（Kling） | 中文视频备选 + 漂移修复 | 中文语义理解强，适合雨夜/泪落琴弦等意象镜头；3.8 方案 A 的图生视频修复工具 |
| Runway | 电影运动镜头 | 相机运动控制细腻，适合 Shot 07 环绕、Shot 15 快速横移 |
| Veo | 复杂镜头 | 若 Shot 17"静帧感"、Shot 15"光影流转"在 H3 上表现不佳，改用 Veo |
| Midjourney | 角色图/场景图（图片版预留） | 后期升级 I2VA/FL2VA 时生成首尾帧参考图（用第六部分图片 prompt） |
| Flux | 真实人物图（图片版预留） | 需要更真实人像的锚定图时使用，忠实度高于 Midjourney |

## 10.2 推荐工作流（纯文字版）

```
0. 准备：通读 3.2/3.3 检查清单；把 L1 锚点串 + 7 条场景锚点串 + 8 段色板词整理到单独备忘文件
1. 母带锁定：将《琵琶曲》歌曲作为唯一 Master Audio（见附 A）
2. 按批次生成：第 1 批女主特写（Shot 02/04/08/11/16/17）→ 第 2 批女主中景（05/06/10/12/13）
   → 第 3 批无人脸场景（01/03/07/14/15/18），prompt 一律从提示词库 / prompt/txt/ 复制
3. 质量门：每镜头采样 3-5 版，按"脸最像 > 服装一致 > 动作自然 > 光影"四关挑选
4. 拼接：按附 A 拼接协议对齐 Master Audio 节拍，硬切拼接
5. 收口：统一 35mm 胶片颗粒 + LUT，歌词字幕按 A.4 规范叠加
6. 验证：全片通看，对照 1.3 歌词-画面表逐句核对 + 附 A.5 检查清单 + 3.10 朝代验收
```

## 10.3 视频规格统一

| 项目 | 规格 |
|------|------|
| 画幅 | 16:9（B站/横屏 MV）；如投抖音可另出 9:16 版（画幅一经选定全片不改） |
| 分辨率 | 1920×1080 |
| 单条时长 | 3-5 秒（≤5 秒，防人物漂移） |
| 单条 prompt | 6000-7000 字符（上限 7000，不含 Negative） |
| 全片时长 | 约 70 秒 |

> ⚠️ 以上画幅 / 分辨率 / 单条时长为**平台生成界面设置项**（H3 生成时选择），提示词文本无法控制，全片统一执行即可。

---

# 附 A：多镜头拼接协议（60-90 秒成片必备）

> 依据 MiniMax `music-video-subtitle-generator` 官方 Skill 的多镜头拼接规范（>15 秒视频必须执行）。

## A.1 全局 Master Audio 锁定
- 以歌曲《琵琶曲》原曲为唯一 Master Audio；所有分镜视频仅提供画面，音轨在剪辑阶段统一对齐；禁止逐条视频自带独立配乐。

## A.2 节拍硬切
- 全部镜头采用硬切（hard cut），禁止淡入淡出（片头 0.5 秒黑场与片尾 2 秒淡出除外）；
- 切点必须落在歌词句首/句尾、鼓点或琵琶重音上；禁止在歌词进行中断切；
- 每镜头时长 = 该歌词句的节拍窗口（参考 1.3 表）。

## A.3 文字延续策略（纯文字版替代"头尾帧延续"）
- 同场景连续镜头（Shot 05→06 江上双舫）：下一镜头 prompt 开头复用上一镜头末尾的环境描写句，实现无缝延续；
- 硬切场景（宫宴→雨夜空楼）：用"动作匹配"衔接——Shot 09 末尾女子衣袖拂动的方向，与 Shot 10 雨丝落向同向，形成视觉动量延续；
- 色彩连续性：每镜头 prompt 末尾的色板词（3.7 表）保证相邻镜头基调一致；收口时用同一 LUT 抹平批差。

## A.4 歌词排版规范（本片为 MV，歌词即画面设计层）
- 歌词以书法感字体（楷体/行楷）作为空间设计层，可居中或偏侧，禁止遮挡眼睛与嘴部；
- 每镜头最多一个主歌词事件；歌词内容必须与所听歌曲逐字一致；
- 出现歌词的镜头：Shot 02（句 1）、Shot 04（句 4）、Shot 11（句 10）、Shot 17（句 16）、Shot 18（尾句字幕）。

## A.5 拼接后检查清单
- [ ] 所有切点落在节拍/歌词句界上，无中途断字
- [ ] 相邻镜头人物锚点串一致（抽查 prompt 文本 diff）
- [ ] 全片服装无变色（Shot 05 与 Shot 12 月白裙逐帧比对）
- [ ] 全片无男性角色入镜（观众视角验收）
- [ ] 全片无清装元素（发式/领型/袖型三查，3.10 验收）
- [ ] 远距离景别可有人但无面部细节（3.9 验收）
- [ ] 女主出声镜头 ≥ 5 个（3.11 台词表核对）
- [ ] 出声镜头全部为说话/独白，无旋律演唱（"说话不唱歌"验收）
- [ ] 统一颗粒与 LUT 已应用，批差不可见
- [ ] 歌词字幕逐字匹配且不遮脸
- [ ] 第 8 段色板与第 1 段色板呼应（首尾呼应验收）

---

# 附 B：原方案不足分析与修改建议（MIX 最终要求）

| # | 原方案不足 | 分析与修改方案 | 本手册落点 |
|---|----------|--------------|-----------|
| 1 | "男主不建议大量露脸"与"第一次眼神交汇"矛盾 | v2.0 升级为男主完全不出镜，眼神交汇改为"观众视角对视"（女主望向镜头） | 2.2、3.4 |
| 2 | 8 段 × 8 秒 = 64 秒，未与歌曲逐句时间轴对齐 | 改为 18 镜头 3-5 秒结构，切点按歌词节拍落 | 1.3、第五部分、附 A |
| 3 | 缺人物一致性方案（原方案仅一句"保持同一女性角色一致性"） | 建立三级文字锚点制度 + 生成纪律 + 批次顺序 + 后期兜底 | 第三部分 |
| 4 | "多年后"阶段无年龄变化规则 | 规定"同脸、低髻、目光更深、零皱纹、同服装"，防被生成成新人 | 2.1、问题 7 |
| 5 | 音乐同步表只列 5 句歌词 | 补齐全部 16 句 + 前奏/间奏/尾奏的镜头对应 | 1.3 |
| 6 | 无统一负面词 | 按人物/画面/身体/皮肤/时代/朝代/质量 7 类建立中英负面词库 | 第八部分 |
| 7 | 无故障排查方案 | 11 个常见问题逐一给解法 | 第九部分 |
| 8 | 未考虑 15 秒单条生成上限 | 按"多镜头拼接协议"拆分为 18 条 3-5 秒短镜头 + 节拍硬切 + 统一收口 | 附 A |
| 9 | 推荐制作方式中"12 段 × 5 秒"无镜头清单 | 18 镜头完整分镜已含时间轴，可裁剪为 12 镜头精简版（删 Shot 09/13/15 的 B 面） | 第五部分 |
| 10 | 未考虑场景一致性 | 建立场景锚点串 + 8 段色板表 + 统一 LUT 收口 | 3.7、附 A.5 |
| 11 | 未考虑远距离人脸崩坏（试点反馈） | 人脸距离规则：**远景可有人但禁人脸**——身体/剪影/背影/局部可入画，面部细节一律禁止；需露脸时用仰角中景 | 3.9、问题 9 |
| 12 | 朝代漂移风险（试点反馈：生成出清装） | 朝代锚定规则：唐代服饰/发型/建筑正向锚定 + 清装负面词 + 三查验收 | 3.10、问题 10 |
| 13 | 人物无声（试点反馈） | 说话不唱歌：女主独白/自语（电视剧式对白+感情词汇），台词分配表（8 镜头出声） | 3.11、问题 11 |
| 14 | 单镜头 prompt 过短、信息密度不足（试点反馈） | 每条视频 prompt 扩写至 6000-7000 字符，独立成库便于复制 | 第七部分、提示词库 |
| 15 | 人物唱歌效果差（试点反馈） | 说话不唱歌：所有出声镜头改说话/独白，感情词汇衬托，prompt 明写 not singing | 3.11、问题 11 |
| 16 | 远景出现人即崩坏（试点反馈） | 远景可有人但禁人脸：身体/剪影/背影入画，面部细节禁止，镜头限制规避 | 3.9、问题 9 |
| 17 | 镜头间无关联、无整体主题（试点反馈） | 每条 prompt 内嵌 story_context：片名/主题/承接落幅/贯穿意象/时空层，形成叙事闭环 | 7.1、提示词库 |

---

> **手册使用提示**：制作时按「1.3 歌词画面表 → 第五部分分镜 → 3.2/3.3 检查清单 → 第七部分检索表 + 提示词库逐镜生成（按批次顺序）→ 附 A 拼接 → 第九部分查障」的顺序执行；所有 prompt 以提示词库为准，禁止另起炉灶手写。

---

# 附 D：歌词全文与镜头对照总表（创作原型）

> 剧本创作原型为歌曲《琵琶曲》完整歌词（含前奏/间奏/尾奏共 20 句）。**v2.1.1：歌词为灵感参考**——镜头从歌词提取意象与情绪后按剧情重新创作（非逐句对应，史书/古城/王朝意象已按此原则删除）；镜头序号与「第五部分 完整分镜设计」一致。

## D.1 歌词全文

> 人间琴悠扬 姑娘把谁记心上
> 南来与北往 美人取情寄琵琶
> 半掩面惆怅 恨只恨泪两行
> 我提笔短叹 你抚琴一世风华
> 东船与西舫 琴音袅袅于心上
> 望姑娘模样 深情终究难放下
> 美人迟了暮 任与绝世共赴
> 卿和了胡旋 君作汉宫琵琶语
> 弹一首琵琶曲 世人争相思意
> 坐高楼赏小曲 抚琴声想起你
> 姑娘不胜酒力 哭的梨花带雨
> 回首人间 笑谈你我初遇
> （副歌重复 ×2 略）
> 弹一首琵琶曲 叹离愁争朝夕
> 坐高楼赏烟雨 烟雨声宛如你
> 思念一夜未停 史书一页未起
> 回首人间 笑谈你我初遇
> 弹一首琵琶曲 世人争相思意
> 坐高楼赏小曲 抚琴声想起你
> 姑娘不胜酒力 哭的梨花带雨
> 今生与你 若只如初遇

## D.2 歌词句 ↔ 镜头对照表

| # | 歌词句 | 对应镜头 | 落地说明 |
|---|--------|:--------:|---------|
| 1 | 人间琴悠扬 姑娘把谁记心上 | 02 | 船头弹琴望月（全片人脸基准镜头） |
| 2 | 南来与北往 | 03 | 长安夜市人潮如流，万盏灯笼 |
| 3 | 美人取情寄琵琶 | 04 | 凭栏弹琴寄情，街心初见 |
| 4 | 半掩面惆怅 恨只恨泪两行 | 08 / 11 | 珠帘半掩面；泪落琴弦（单泪凝练） |
| 5 | 我提笔短叹 你抚琴一世风华 | 14 / 08 | 指间岁月（琴身包浆、雪融成泪，弱相关）；珠帘后独奏 |
| 6 | 东船与西舫 | 05 | 江上双舫并舟，琴音相和 |
| 7 | 琴音袅袅于心上 | 06 | 手部特写拨弦；对面船琴声相和，指尖微顿后相和（相知事件） |
| 8 | 望姑娘模样 深情终究难放下 | 04 / 16 | 街心仰望 / 重逢回眸 |
| 9 | 美人迟了暮 任与绝世共赴 | 12 | 多年后江岸，同脸低髻，目光更深（延伸 13-15 时光无声段） |
| 10 | 卿和了胡旋 | 07 | 宫宴胡旋群舞全景 |
| 11 | 君作汉宫琵琶语 | 08 | 珠帘半垂，席间独奏 |
| 12 | 弹一首琵琶曲 世人争相思意 | 12 | 多年后独奏，琴声传世人 |
| 13 | 坐高楼赏小曲 抚琴声想起你 | 04 | 她坐高楼弹琴，观众街心仰望 |
| 14 | 姑娘不胜酒力 | 10 | 雨楼独饮，双杯一杯未动 |
| 15 | 哭的梨花带雨 | 11 | 泪落琴弦，琴音顿止 |
| 16 | 回首人间 笑谈你我初遇 | 16 / 17 | 时间倒转回初见街巷，回眸定格微笑 |
| 17 | 弹一首琵琶曲 叹离愁争朝夕 | 12 / 13 | 江岸独奏 → 四季江岸（时光无声：岁月环绕而不改变她） |
| 18 | 坐高楼赏烟雨 烟雨声宛如你 | 10 | 雨声如故人（prompt 已写明雨声似其声） |
| 19 | 思念一夜未停 史书一页未起 | 13 / 14 | 四季江岸（思念未停）；指间岁月（雪融成泪落弦，呼应镜 11） |
| 20 | 今生与你 若只如初遇 | 16 / 17 / 18 | 重逢 → 定格微笑 → 终章字幕落款 |
