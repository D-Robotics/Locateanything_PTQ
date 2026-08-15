# Stage 6: fast_336 Language 构建

> 历史基线记录：本页 HBM 的 Prefill/PBD/AR Logits 为 `1/q/q`，不包含 fused Prefill 或 Compact Logits。当前目标 ABI 为 `7/6/1`，必须使用新的校准 Scale 和独立输出目录重新构建。

## 状态

已完成并通过验收。13 个 Source BC、13 个 Converted BC、13 个 4-Core HBO、Token Embedding 和最终 Language HBM 均已构建；独立 `--resume` 复验和 13 图 HBM ABI 审计均通过。

## 实际配置

| 参数 | 值 |
| --- | ---: |
| Prefill | 256 |
| KV Cache | 1024 |
| PBD Query | q6-q12 |
| AR Query | q1-q5 |
| Decoder 权重 | W8 |
| LM Head 权重 | W8 |
| KV Cache 边界 | Source BC FP32；Converted BC / HBO / HBM INT8 |
| Logits 边界 | FP16 |
| March | nash-p |
| Prefill / PBD / AR Core | 4 / 4 / 4 |
| 编译 Jobs | 16 |
| Sampling | Host |

固定 13 图：

```text
prefill
decode                 # PBD q6
decode_pbd_q7-q12
decode_ar              # AR q1
decode_ar_q2-q5
```

## 输入

| 输入 | 路径 |
| --- | --- |
| Float 模型 | `/home/kangjie.xu/ptq_acceptance/20260814_105905/Locateanything_PTQ/compiler/models/LocateAnything-3B` |
| fast_336 配置 | `compiler/config/fast_336.yaml` |
| 1200 样本 Scale | `compiler/outputs/fast_336_prefill256_cache1024_w8/calibration/statistics/calibration_scale_manifest.json` |
| Scale Manifest SHA256 | `06968b05f1e2524fe90ebd081bc2165e7308a9619660fa9b92110d00b30ef1dd` |
| 构建输出 | `compiler/outputs/fast_336_prefill256_cache1024_w8/build/language/` |

Stage 4 对每个 Language 图生成 1393 个校准上下文，289/289 个激活点有效，Decode Context Coverage 通过。

## 执行命令

```bash
/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/quantize.py \
  --config compiler/config/fast_336.yaml \
  build --component language --target bc --resume

/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/quantize.py \
  --config compiler/config/fast_336.yaml \
  build --component language --target hbm --resume

env PYTHONPATH=compiler \
  /home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/pipeline/hbm_audit.py \
  --bc-dir compiler/outputs/fast_336_prefill256_cache1024_w8/build/language \
  --hbm compiler/outputs/fast_336_prefill256_cache1024_w8/build/language/LocateAnything-3B_language.hbm \
  --report compiler/outputs/fast_336_prefill256_cache1024_w8/reports/language_hbm_contract.json
```

## 完成数量与结果

| 项目 | 结果 |
| --- | --- |
| Source BC | 13/13，通过 75 输入、73 输出 ABI 校验 |
| Converted BC | 13/13，KV 输入和更新均为 INT8 |
| 4-Core HBO | 13/13，可由 `Hbo` 重新打开 |
| Language HBM | 1/1，含固定 13 图 |
| Token Embedding | 1/1，`625381376` bytes |
| Source BC Pipeline | `277.9s`，`exit_code=0` |
| HBM 收尾 Pipeline | `11737.4s`，`exit_code=0` |
| 独立 `--resume` 复验 | `700.3s`，`exit_code=0` |
| HBM ABI 审计 | `291.1s`，13/13 `passed` |
| `.partial.*` | 0 |

HBM ABI 审计报告：

```text
compiler/outputs/fast_336_prefill256_cache1024_w8/reports/language_hbm_contract.json
```

审计确认 13 个 Linked HBM 图分别与同名 Converted BC ABI 一致。典型图契约如下：

| 图 | Hidden State | Position | Mask | KV 输入 | Logits | KV 更新 |
| --- | --- | --- | --- | --- | --- |
| `prefill` | `(1,256,2048)` FP16 | `(1,1,256)` INT32 | `(1,256,1024)` FP16 | 72 x `(1,1024,2,128)` INT8 | `(1,1,152681)` FP16 | 72 x `(1,256,2,128)` INT8 |
| `decode` | `(1,6,2048)` FP16 | `(1,1,6)` INT32 | `(1,6,1024)` FP16 | 72 x `(1,1024,2,128)` INT8 | `(1,6,152681)` FP16 | 72 x `(1,6,2,128)` INT8 |
| `decode_ar_q5` | `(1,5,2048)` FP16 | `(1,1,5)` INT32 | `(1,5,1024)` FP16 | 72 x `(1,1024,2,128)` INT8 | `(1,5,152681)` FP16 | 72 x `(1,5,2,128)` INT8 |

## 产物清单

Source BC 路径模式：`LocateAnything-3B_language_chunk_256_cache_1024_decoder_w8_lmhead_w8_nash-p_corenum_4_4.<graph>.bc`。

| Source BC 图 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| `prefill` | 3090407691 | `885a79c887bcb190cc4721552e3df45d226da916588e51cd83a0a3e7e89169d6` |
| `decode` | 3090415060 | `9dd4eb479ed2792b6b756530ad8a28ce78cd79abdece71191ac3852100af61ed` |
| `decode_pbd_q7` | 3090415067 | `f7a9f935e2e0a7e3e328bff2c595a0fba7efbca8bf4ea2c9bb814648c3aace13` |
| `decode_pbd_q8` | 3090415059 | `a5b884c5282d354f4a89e11f5dfde66b675bf15744c510ba0cdda086f54f18dd` |
| `decode_pbd_q9` | 3090415071 | `8030e6dff83a275a08328f5a5df2fb32ddb076bccac7e2ac697d5f05551d88f5` |
| `decode_pbd_q10` | 3090415077 | `591e0e00bb6268252633445075d9c0f17746c4720ec2bf973f1cc2385a372dae` |
| `decode_pbd_q11` | 3090415077 | `1148389b1c81d9920fe652049acf281cc7bdc343fc103120095d9e29c4987087` |
| `decode_pbd_q12` | 3090415077 | `4d51b296c8f8196996ea727f34109437236661842ab9b05d170787cfe9c8780b` |
| `decode_ar` | 3090407490 | `9d6ae56a6b7ea4e249fe6c9b43c65f41fd93019d5225779efc6fd944c703b136` |
| `decode_ar_q2` | 3090414932 | `01586f0ada97d58cef82087f8ff8c02e08664c809cc7673c6f0a602537fbb2fd` |
| `decode_ar_q3` | 3090415054 | `93f7f0d13cec0888d3b2b50a068172592e7a1fbb3dd52aae7928d0de0ecf790c` |
| `decode_ar_q4` | 3090415066 | `081d0f70464773f3445843062703336cc34e7f1ba60f1e3f28a8717d9c7b1927` |
| `decode_ar_q5` | 3090415066 | `54e94577913a81e8f8753b29e5cde21d010202c9b26fa1dbca680b5fc15bf9ec` |

| Converted BC 图 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| `prefill` | 3093487962 | `44ea63d90dc6dadff7536fcc898ba2355a7b12d271fb87159319d5223ee4b380` |
| `decode` | 3093496072 | `0c56d9adff13b8ad4e46fc6b15f208eb99689477d620dfc64bcec724b2185ed2` |
| `decode_pbd_q7` | 3093496087 | `2fd6d7fb0d4995ef3540c635a2566b8655d96bcc71dda96a5d6ff113ab2941a8` |
| `decode_pbd_q8` | 3093496095 | `9a50dc08b3b63a3eac2fae0c46b734780fc25cc8a69492db0ae107534a12fc26` |
| `decode_pbd_q9` | 3093496100 | `a4e646cc14488f68999c170f1643826db80e7db45466517edf05d9ecdf9b0b04` |
| `decode_pbd_q10` | 3093496097 | `2d6e3526937c19d8429a4320223d8fd970c654ac45c956b6d99ed192c5eb0f39` |
| `decode_pbd_q11` | 3093496097 | `c0d3c634c9498bbebd497e9d703fdbc3f0c27da6be774b82aa79147e806af8ab` |
| `decode_pbd_q12` | 3093496098 | `cd6fe35b586afe472dc5f0d737708d3ea4d4b55fc4455fecd872298b8cb8e967` |
| `decode_ar` | 3093488720 | `a18e9b277a22d320d82e58e5b03fc76aaf099098a1a8297e2c5a2576b3051636` |
| `decode_ar_q2` | 3093495995 | `583419857cafd59739a39f3c04037b48c9e25143857b0f3264d1bfa617ffb2d2` |
| `decode_ar_q3` | 3093496069 | `7701252fa872cc759ce9654004982d3ebd6ff23cc4d03632b9981e32bc9f0d00` |
| `decode_ar_q4` | 3093496083 | `9a11264a4e09710b4dee175bb9e4083aa2905d16dd560d01bf9fa889112e6155` |
| `decode_ar_q5` | 3093496084 | `03e500edcff340bf1657338907cd9f23a565d80eb4d5bd2b832e46cc3cc917c9` |

| HBO 图 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| `prefill` | 3197492552 | `f5c229ae203ff58c02c1f52172f0f563f68f4736523210e187aa2f1ac3856559` |
| `decode` | 3173628552 | `68d2e7d60c1c91e17f51e81bc481bbee97aee81f6563fc4f211b08f95c003e24` |
| `decode_pbd_q7` | 3179516792 | `e5bc08d3e695130205215ee1fe5e4e8cf564bff15e521d2c251696cb47751f42` |
| `decode_pbd_q8` | 3176427640 | `57020c02a24702f3b2f7b2058be9ac80e76e95d04707708e8ce9b5b8bc204a7f` |
| `decode_pbd_q9` | 3178369912 | `182fabd02855ca40c287192f24181a9a8cf04f8d03162112628e577294392b1c` |
| `decode_pbd_q10` | 3177861384 | `60f1f9a442ed4fbcb946f195dbb3dd9ec92278c32503298f24ec96056fba4c76` |
| `decode_pbd_q11` | 3176474376 | `4e135119854ddf13c7362ad3e562f946add4c4b6e3bf716095bed185537e1727` |
| `decode_pbd_q12` | 3177449992 | `15e4ac764bbb8689bb0e189dc92b120552e6fb49025f2556c1f333b2e0cb50b6` |
| `decode_ar` | 3174024408 | `de6d4ffabd1f6e4bbae1bfe9759fdf04a1b63f975306faddf075cfe3d4c2436` |
| `decode_ar_q2` | 3174259432 | `8f3de1a487ff89899e0a3d7e52bbb57b947d8fb679150d55f13f84c1fe22a264` |
| `decode_ar_q3` | 3174459624 | `9212b6a6e31db3ac5f73a75ba468e0d1344e458ee7f9746c1cb05f7c3670245e` |
| `decode_ar_q4` | 3173089256 | `2ad4581f7434e23d9e61185f5417ce9693468db8dd92d9460a415e212bd51380` |
| `decode_ar_q5` | 3173710824 | `16f77c0d7aba87728c0b5c0175a2d95b0d3f02402a3f01b430589623321ab49c` |

| 其他产物 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| `LocateAnything-3B_language.hbm` | 3467789616 | `6ff906d7fd236530c42872b20055c3b7ea1b9abcf2ebe324eca07c9985bbec41` |
| `LocateAnything-3B_embed_tokens.bin` | 625381376 | `8668944fcb527faf3bbcd1c03a88d9da69f400b0700028f51ac6abe700e04011` |

## 问题与偏差

- 首次 HBM Pipeline 在 `decode_ar_q3` 100% 后被系统以 `SIGKILL` 终止，退出码 `137`；该尝试已保留为 `logs/build_language_hbm.attempt1.exit137.log`。
- 当时主机无 Swap，长生命周期编译进程的累计内存占用升至约 106 GiB。恢复时未修改代码、Profile、量化参数或输出目录，仅以同一命令的 `--resume` 在干净进程中复用已完整落盘的 10 个 HBO。
- 恢复进程完成 q3、q4、q5 和 HBM 链接；最终独立 `--resume` 复验和 HBM ABI 审计均为通过。
- 4090 上的 ABI、产物完整性和可重开验证不等同于 S600 的数值、任务语义、时延或资源占用验收。

## 结论与下一阶段门槛

Stage 6 通过。fast_336 Language 的 13 图 W8A8 HBM 已完成，并以独立复验和 HBM ABI 审计确认。

下一阶段为 Stage 7 S600 对比验收。开始前须单独列明板端输入、部署产物、测试命令、对比任务、性能与精度门槛；在此之前不得把 4090 编译通过表述为 S600 推理通过。
