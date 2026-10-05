# MM·H3 工作台 模型下载与放置指引

> 本安装包**不包含模型权重**。MM·H3 工作台使用 **MiniMax H3 官方开源模型**
> （MiniMax H3 Community License 约束，详见 `NOTICE`），请按下表从魔搭社区
> （ModelScope）等官方渠道下载后，放到安装目录 `model\` 对应子目录。
> 全部 8 个文件合计约 **90.2 GB**，请预留不少于 95 GB 磁盘空间。

## 一、快速步骤

1. 打开魔搭社区 <https://modelscope.cn>，搜索 **MiniMax-H3**（发布方以 MiniMax 官方组织为准），
   进入模型仓库的「模型文件」页；
2. 按下表逐个下载 8 个文件（类别列即目标子目录名）；
3. 将文件放入安装目录（默认 `%LOCALAPPDATA%\Programs\MMH3Workbench`）下
   `model\` 对应子目录的**顶层**（不要建二级子目录）；
4. 重启 MM·H3 工作台，壳启动画面不再出现「未检测到模型权重」提示即就位成功。

> 国内网络推荐魔搭；也可从 HuggingFace `MiniMax-AI/MiniMax-H3` 等官方镜像下载，
> 文件名以下表为准（模型仓库如有多版本文件，优先与本表同名文件）。

## 二、文件清单与放置位置

| 目标子目录（model\ 下） | 文件名 | 大小 |
| --- | --- | --- |
| `diffusion_models` | `MiniMax_H3_FL2VA_pruned_int8_convrot.safetensors` | 19.53 GB |
| `diffusion_models` | `MiniMax_H3_Ref2VA_nvfp4_mixed.safetensors` | 22.76 GB |
| `diffusion_models` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 22.76 GB |
| `text_encoders` | `qwen3vl_32b_minimax_h3_abliterated_nvfp4.safetensors` | 16.64 GB |
| `vae` | `minimax_h3_video_vae_fp16.safetensors` | 4.85 GB |
| `vae` | `minimax_h3_audio_vae_fp32.safetensors` | 0.56 GB |
| `loras` | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.82 GB |
| `loras` | `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 1.82 GB |

放置后的目录形态（节选）：

```
MMH3Workbench\
└─ model\
   ├─ diffusion_models\
   │  ├─ MiniMax_H3_FL2VA_pruned_int8_convrot.safetensors
   │  ├─ MiniMax_H3_Ref2VA_nvfp4_mixed.safetensors
   │  └─ minimax_h3_ref2va_pruned_int8_convrot.safetensors
   ├─ text_encoders\
   │  └─ qwen3vl_32b_minimax_h3_abliterated_nvfp4.safetensors
   ├─ vae\
   │  ├─ minimax_h3_video_vae_fp16.safetensors
   │  └─ minimax_h3_audio_vae_fp32.safetensors
   └─ loras\
      ├─ minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
      └─ minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
```

## 三、判别就位是否成功

- 壳启动时自动扫描 `model\` 四个类别目录的**顶层文件**：目录存在且至少有一个
  有效权重文件即视为该类别就绪（`desktop.ini`、`put_*_here` 占位文件不算）；
- 也可以直接在页面上发起一次生成做最终确认（模型在首次推理时按需加载）。

## 四、附注

- **推理环境**：本工作台的推理依赖 CUDA GPU（显存建议 ≥ 16 GB）与对应
  Python 运行时；若安装包未附带 `runtime\`，请参照项目 README 准备
  Python 3.10+ 环境并安装 `requirements.txt`（torch 需 CUDA 版）。
- **开发机共享权重**：若本机已有 ComfyUI 且已存放 H3 权重，可不对拷文件，
  在仓库 `model\` 下按类别建 Windows Junction 指向 ComfyUI 的对应目录即可
  （Junction 创建无需管理员权限，对应用完全透明），参见开发仓库
  `model/README.md` 的做法。
- **许可提醒**：MiniMax H3 Community License 存在地域限制（欧盟/英国/韩国/美国）
  与商用门槛（年收入超 2000 万美元需事先获得 MiniMax 书面授权），商用前请阅读
  `NOTICE` 与 `docs/MiniMax-H3-Community-License.txt`。
