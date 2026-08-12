# 官方语料数据缺口逐条审计

- 已验证源码 HEAD：`414a9803964a61ffa1876b9d1bbda0fba0e6a298`
- 严格迁移缺口：`53` 条问句
- 未解析范围词：`57` 个，累计 `76` 次
- 强制模糊映射：`0`

> 本报告把数据缺失、事件语义、域外资产、歧义名称和疑似错误分开。确定性拒绝不是编译成功，也不计入正确率，但能防止生成语义错误的 SQL。

## 决策汇总

| 决策 | 范围词数 |
|---|---:|
| `implement_derived_rule` | 9 |
| `optional_domain_extension` | 4 |
| `pending_external_dataset` | 16 |
| `reject_ambiguous` | 18 |
| `reject_invalid` | 10 |

## 逐项裁决

| 范围词 | 出现次数 | 分类 | 竞赛处理 | 涉及Excel行 | 原因与下一步 |
|---|---:|---|---|---|---|
| 英美贸易业 | 3 | `ambiguous_nonstandard` | `reject_ambiguous` | 1386 | 不是可确认的交易所或主流行业分类名称，英美也可能表示地区而非行业。 需要出题方给出分类体系和成员定义；此前保持确定性拒绝。 |
| 音频媒体行业 | 3 | `vendor_snapshot_candidate` | `pending_external_dataset` | 1459, 1460 | 可能对应媒体或音频内容板块，但没有唯一行业代码。 只接受完整、带日期的分类来源快照，不做近义词猜测。 |
| 100429 | 3 | `suspected_invalid` | `reject_invalid` | 1508 | 不符合当前官方证券代码目录中的可确认标识。 保留原文并返回证券标识无法确认。 |
| 上海中环概念 | 3 | `ambiguous_nonstandard` | `reject_ambiguous` | 1802 | 名称可能指地区、公司或临时题材，没有统一成员定义。 仅在获得明确板块代码和完整成员表后接入。 |
| 石膏石材板块 | 2 | `vendor_snapshot_candidate` | `pending_external_dataset` | 177, 208 | 可能存在于供应商行业或题材分类，但不是统一行业标准名。 要求来源给出板块代码、全量成员和快照日期。 |
| 印花板 | 2 | `ambiguous_nonstandard` | `reject_ambiguous` | 222 | 可能是错词、材料名称或自定义板块，无法唯一解释。 不做编辑距离映射，等待明确语义。 |
| 大订单 | 2 | `derived_semantics` | `implement_derived_rule` | 385 | 更像基于订单或资金流字段计算的事件条件，不是静态证券成员集合。 接入有明确大单口径的逐笔或资金流数据后实现事件规则。 |
| 深证龙科 | 2 | `suspected_invalid` | `reject_invalid` | 847 | 无法在证券和指数身份目录中确认该名称。 返回标识无法确认，不自动替换为相似证券。 |
| 香港金科 | 2 | `suspected_invalid` | `reject_invalid` | 847 | 名称不能唯一对应可交易证券，且可能超出A股范围。 需要完整市场代码后才能进入可选资产扩展。 |
| 美的科技 | 2 | `ambiguous_nonstandard` | `reject_ambiguous` | 1168 | 可能指公司简称、供应链或概念，不能唯一对应美的集团。 只接受明确证券代码或板块代码。 |
| cvpr | 2 | `vendor_snapshot_candidate` | `pending_external_dataset` | 1540 | 会议名称可形成临时题材，但没有稳定、统一的上市公司成员标准。 如使用资讯平台口径，必须固定来源和采集日期。 |
| 连扳概念 | 2 | `derived_semantics` | `implement_derived_rule` | 1749, 1773 | 疑似“连板”错写，核心语义应由连续涨停行情推导，而不是静态概念表。 先记录错词裁决，再按涨停规则和连续交易日实现事件算子。 |
| 深鱼子油 | 2 | `suspected_invalid` | `reject_invalid` | 1758 | 无法确认是证券、行业或公开概念名称。 保持拒绝并要求明确原始名称。 |
| 北京国投 | 2 | `ambiguous_nonstandard` | `reject_ambiguous` | 1758 | 可能对应多家机构或国资关系，缺少唯一证券代码。 需要法人主体代码或明确控股关系口径。 |
| 科技电池 | 2 | `ambiguous_nonstandard` | `reject_ambiguous` | 5313 | 是多个宽泛词的组合，不能确定具体行业或概念。 不得拆词后任意取并集；需要正式板块代码。 |
| 幕墙板块 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 229 | 可以作为供应商板块，但缺少统一行业代码和历史成员。 获取完整快照后按供应商口径接入。 |
| 能源技术服务 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 251 | 接近行业描述，但不同分类体系的边界不同。 绑定明确分类体系、层级和行业代码后导入。 |
| 混凝土概念 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 264 | 属于供应商题材口径，没有跨平台唯一成员集。 只接入完整、带日期的概念快照。 |
| 白酒ETF | 1 | `out_of_official_domain` | `optional_domain_extension` | 288 | ETF不属于官方A股个股行情主域，且名称可能对应多只基金。 作为独立基金资产插件处理，必须提供基金代码和基金行情表。 |
| 大订单概念 | 1 | `derived_semantics` | `implement_derived_rule` | 386 | “大订单”应有成交或订单阈值，不应伪装为静态概念成员。 明确阈值和数据字段后实现事件筛选。 |
| 东方空间 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 406 | 可能指未上市商业航天企业或相关产业链，不能当作单一A股证券。 需要明确是公司主体还是供应链概念。 |
| 影子股 | 1 | `derived_semantics` | `implement_derived_rule` | 411 | 属于策略关系概念，成员取决于参照公司和关联规则。 定义关联关系、参照标的和有效期后形成关系算子。 |
| SaaS产品 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 422 | 可作为主题分类，但供应商口径和时间变化明显。 仅使用版本化概念快照，不倒推历史成员。 |
| 第十代火箭 | 1 | `suspected_invalid` | `reject_invalid` | 425 | 没有可核验的标准证券范围或行业定义。 按噪声或错误输入拒绝。 |
| 深远光大 | 1 | `suspected_invalid` | `reject_invalid` | 430 | 无法对应官方证券身份，可能由多个名称片段误拼接。 不做相似名称替换。 |
| 第一代锂电池 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 445 | “第一代”没有统一行业边界，无法形成确定成员集。 需要出题方给出技术分类标准。 |
| 第十代半导体 | 1 | `suspected_invalid` | `reject_invalid` | 451 | 不是通行的半导体代际分类名称。 作为语义异常拒绝。 |
| 国企重组 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 516 | 可形成事件主题，但成员随公告和供应商口径变化。 使用公告事件或版本化概念快照，禁止使用无日期常量名单。 |
| 成都国资委 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 516 | 需要股权控制链和报告期，不能仅靠公司简称推断。 接入带日期的实控人或股东关系数据后实现。 |
| 高薪华为链 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 516 | 疑似错词且“华为链”本身为供应商主题口径。 要求确认原词和成员定义。 |
| 擒牛火箭 | 1 | `derived_semantics` | `implement_derived_rule` | 519 | 属于策略黑话，不是数据供应商可权威给出的证券范围。 只有在给出价格形态公式后才能实现为技术模式。 |
| 高温超导带材 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 575 | 属于细分产业主题，缺少统一上市公司成员标准。 采用带日期的产业链快照并标明供应商口径。 |
| 真空室内的第一壁 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 575 | 属于核聚变设备细分术语，不等于稳定证券板块。 需要可核验产业链数据集和成分依据。 |
| 偏滤器 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 575 | 属于核聚变设备部件，证券映射依赖产业链研究口径。 仅接入有来源和日期的产业链成员表。 |
| AI加行业板块 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 609 | 缺少被组合的具体行业，无法确定集合交并关系。 要求输入改写为明确的AI概念与具体行业表达式。 |
| 光铜共进概念 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 613 | 属于通信产业主题口径，不是统一行业分类。 使用完整概念快照并固定采集日期。 |
| 短线 | 1 | `derived_semantics` | `implement_derived_rule` | 615 | 表示交易周期或策略风格，不是证券成员范围。 需要配置明确的交易日窗口，不能当作scope_membership。 |
| 腾讯蓝包概念 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 636 | 名称无法对应稳定公开概念，可能是临时事件或错词。 要求提供正式概念名、代码或成员表。 |
| 龙回头 | 1 | `derived_semantics` | `implement_derived_rule` | 638 | 属于价格和涨停序列形成的策略形态，不是静态板块。 明确涨停、回撤和再次走强的参数后实现事件算子。 |
| 火箭阳 | 1 | `derived_semantics` | `implement_derived_rule` | 750 | 属于K线策略术语，定义依赖涨幅、实体和成交量阈值。 得到公式后通过日行情实现技术模式。 |
| BLacKweLL | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 763 | 可对应Blackwell产业链主题，但成员属于供应商研究口径。 规范大小写后仍需完整、带日期的概念成员表。 |
| 二十几题财 | 1 | `suspected_invalid` | `reject_invalid` | 773 | 无法形成可解释的金融实体或范围，疑似噪声文本。 保留输入证据并拒绝。 |
| 腾讯霸主 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 773 | 属于描述性短语，没有可验证成员规则。 要求改写为明确证券、概念或业务指标。 |
| 深圳电信 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 788 | 可能是分公司或地区业务主体，不是可唯一确认的独立A股证券。 需要统一社会信用代码或明确上市公司代码。 |
| MATE70 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 929 | 属于产品产业链主题，成员随供应商口径和时间变化。 仅使用带版本的产业链快照。 |
| 腾讯控股 | 1 | `out_of_official_domain` | `optional_domain_extension` | 1275 | 是港股证券，不在官方A股日行情主表范围内。 作为港股资产插件接入独立行情表，不能映射成A股。 |
| 杨氏纸业 | 1 | `suspected_invalid` | `reject_invalid` | 1292 | 无法在官方证券身份目录中确认。 返回证券不存在或待确认。 |
| 沪上阿姨 | 1 | `out_of_official_domain` | `optional_domain_extension` | 1297 | 对应港股上市主体时仍超出官方A股数据域。 只有提供港股代码和港股行情表后才启用。 |
| 港湾经济 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 1385 | 可能是区域经济概念，但没有统一边界和成员标准。 需要明确区域范围、产业口径和有效期。 |
| 994338 | 1 | `suspected_invalid` | `reject_invalid` | 1505 | 不符合当前可确认证券或指数代码。 不自动纠错为相近数字代码。 |
| 破镜 | 1 | `derived_semantics` | `implement_derived_rule` | 1647 | 更像策略形态简称，不是证券成员范围。 要求提供可计算的价格序列定义。 |
| 推进 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 1697 | 普通动词不能唯一解析为证券范围。 要求补全上下文。 |
| 能源 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 1752 | 可能指行业、主题或指数，范围过宽且分类体系未指定。 要求指定中证、申万、证监会或供应商板块代码。 |
| 深海鱼处理行业 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 1759 | 不是可确认的标准行业分类名称。 需要给出分类代码或成员清单。 |
| 运动用品 | 1 | `vendor_snapshot_candidate` | `pending_external_dataset` | 3382 | 可对应消费品细分行业，但不同分类体系边界不同。 绑定明确行业体系和代码后接入。 |
| 指数基金 | 1 | `out_of_official_domain` | `optional_domain_extension` | 3702 | 是资产类别而非唯一证券范围，官方主数据未提供基金域。 建立基金主表、跟踪指数关系和基金行情后作为独立插件启用。 |
| 螃蟹 | 1 | `ambiguous_nonstandard` | `reject_ambiguous` | 3981 | 普通名词没有可验证的金融范围定义。 不构造臆测概念成员，要求明确语义。 |

## 使用规则

1. `pending_external_dataset` 只有取得完整成员、时间版本和来源许可后才能转为已解决。
2. `implement_derived_rule` 应实现为行情或事件算子，禁止写入静态成员表。
3. `optional_domain_extension` 属于基金、港股等额外资产域，不影响官方A股基线。
4. `reject_ambiguous` 和 `reject_invalid` 保持确定性拒绝，不使用字符串相似度猜测。
