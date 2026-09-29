# History rewrites before publication

Before the repository was first published (2026-09-29) its Git history was rewritten twice, at the owner's request:

1. The Free Edition workspace URL in the capability report was replaced with `<workspace-host>` in every commit.
2. Private working files were removed from every commit: AI-agent instructions and planning prompts, launch/LinkedIn drafts, the agent's progress ledger, regenerable workspace staging copies, an unimplemented dashboard skeleton and a superseded dashboard export. Local copies are kept outside version control.

Evidence files, run IDs (for example `final-native-v2-aeea7734d3c9`) and the freeze manifest (`code_sha` `c5fdacc…`) record **original** commit SHAs. Use this table to find the published commit. Run IDs are not renamed.

| Original SHA | Published SHA | Subject |
|---|---|---|
| `6b31de4566dab89950e384ba238231ff05a4605d` | `d12ff05542f8cae75506fc37e0a1786c25e004d2` | Scaffold NYC 311 forecasting benchmark and validate local adapters |
| `c73bb03722d31e2e708abdee002c3e4fa23f8bb3` | `0d724448b7c52763e43514560544ec13a44e36e9` | Reconcile 2021-2024 NYC aggregates and freeze development series |
| `465aa7ba6c7264bb82be844b8d5f0f47c5d28458` | `9b60a687e05097ad770bec9b828f6c646a87a9c2` | Add bounded real-data adapter smoke runner |
| `d5a1bccfc29c065d7d50ea998f845078fb56151d` | `8403eff66b4e6394e8499c10bcc71c9226813848` | Record three-series development adapter smoke evidence |
| `5350b2824b0053d8e0a266b78312be4364153083` | `bed7809a8e28bb3c6fab62960ca311210c33a98e` | Implement paired evaluation and development champion rules |
| `f2931d741615861bdce9f497ce6ad9624c578e6a` | `a035ebc38c430caad23a7f8a03553f1284613a9a` | Verify Databricks development Silver deployment |
| `1f7371748da6c9f9100545869624a04df947f97e` | `baa9c400b84030acb8056d0abbac4d0b1035c1e6` | Record native v2 runtime dependency blocker |
| `3986bbd7d7421ea65eab47a4df2da3e41122e076` | `1c64e34d45dfc97584cbb3932a433cdee07c206b` | Add bounded two-origin development slice runner |
| `84b6ec67315f3657474cba27467f1ba9ac501a61` | `6e993bd2a3a9a430400cdf798666deb76eebb4f3` | Record two-origin local development slice |
| `2e84df4ed954b82f93a90b4b9fc32ebe573ca006` | `16ac9fcf7974accd52b223b31e1dc493de93c7fb` | Deploy and verify serving views |
| `7791d34f5b5a7d052e094cc8d9df70fe9d8b056e` | `99c40c1a980f4f3b1d9083a8f95474c68e1ed4e3` | Create and verify unpublished development dashboard draft |
| `df7bc516941af31ced5d44dd77ebedc6ba9f5718` | `3cbb07d1624511eeaa9498112c07ef959612cac5` | Load verified source and series lineage metadata |
| `44e8dcb62a93647b7ff0ec186610e821dd339544` | `d6efd97715d2aafc1c1139d85af38461dd763c72` | Preserve hashed JSON payload line endings |
| `e51521df538bb68ef2bed42433d00af4724acf53` | `ee61f3ce5764491deb0c98dd593678538d9f4d77` | Serve reconciled development data quality |
| `d47dda59a5aa83a4c97324612b741cdd85954354` | `6a2d352cb126d28fc4470474f37f0c5329b1b6a9` | Refresh next milestone after data-quality deployment |
| `31ee879fa73d0f4e7e81c88fa35ad481d8f96afb` | `3896d7fda9ca47221a54c05daf5bb9633147c174` | Persist development smoke and extend readiness evidence |
| `66ee77ad9d8770f68046c49d02c7767a9a7d3971` | `c8c857bf69cc4cada55c655621a0a2da8812803e` | Record bounded Prophet development tuning smoke |
| `3afb8b112a160c75db2c173cfdb564af26702fea` | `b154628e964d67f79155d2613c7853f42ca38d10` | Record Free Edition v2 access blocker |
| `30862cc33ddc821e88724a68157184fa2583cfcb` | `bbe1a5cf2b7e503c69fba2fee8f1704f83529bbe` | Complete Prophet tuning and prepare two-model development run |
| `0d96d7e8d834fec2c66fc855a818c52e8418ed75` | `cd264f9fe5da1d4b2db2993cb0dd05e649c9b139` | Verify and present 2024 two-model development results |
| `7220f6bb416b2b189ded2ea24a0bd938ad0289e4` | `414767ebf24d194db2c55980c130a56dfa049577` | Add freeze gate and deploy development jobs as a bundle |
| `059bfe7b4f93de2f9a9fcf7e39387fce2a60d5da` | `c3ca8b0be049327d099ec88f5fb2e04dfb06e6fe` | Independently re-verify ai_forecast v2 blocker |
| `52563c6470ea9319206788acbed36539f1714d2d` | `7593067afd6f2101eb516fbd540ae105b8bc748a` | Record serverless egress probe; LinkedIn route exhausted for v2 |
| `60e97c09e4cfb23255c98c7e6191c19e5268c3f1` | `a051dbc77df8349c8cbfdc04f522d594c3eea810` | Record v2 smoke failure in trial workspace |
| `d6ff569be4b03825ecd56ee4fcf83a863f08abad` | `bb3b8e765d6109c60c116d66a334d4a79cd22d56` | Record trial v2 attempts after networking preview |
| `378e4477604ad5e85acb1bb8f80c56ce3b1fb44b` | `04f729cc58964ccd38ca2b2df233a5662ba54d59` | Verify ai_forecast v2 in trial workspace; request inclusive horizon |
| `fe9f8b2e98fabacbfec25b525aa2673cca68c472` | `24e197983b52b92d451e30eeb7f34ba7d1bab70a` | Add v2 development runner and trial workspace Silver load |
| `f640d1928e958c4f6e1d7b9fdc30690705adf491` | `7c7f6fa547847ed2d7e3e11a89d2bea1fb58bc5d` | Record one-series v2 development pilot |
| `c5fdacc0d163290b7e0a23a301848a2534a2b6df` | `e5675825f2b42f08c4bac17c5b107b9a36ed5fcd` | Complete three-model 2024 development grid and register deviations |
| `42ce7907ea9ed4065f0670b913a7949f9c1dcc78` | `bf8cda105e9eadfd46fb1bab0ba5fb7bda4d9bd0` | Freeze benchmark protocol v1.0 |
| `76e1857a3370adf134486da8ba030e529317c2d5` | `f91396667724cf36869ad8749c83d375b424a6d8` | Add frozen final benchmark stages and 2021-2025 Silver materializer |
| `31b8abeb72deb81d1317665e67e2d83a5b2cfef3` | `aa7a5fd08b5033b947f6042cd72b60daf6c4f04c` | Add 2025 evaluation snapshot and 2021-2025 Silver after freeze |
| `652b3f66baac4cef0ac5a6d6e39d77436928cb39` | `8e67c1408ed00b20ccf7fecacf438e622adf8f15` | Tie final runs to development tuning lineage; parameterize Silver load |
| `10cc5e39cfde2b846eca6ecd2454a51490b029bb` | `a19eeaa59f19c495acb8c9d074ee0f5702575346` | Fix final lineage test expectation |
| `80e0a12bdce76589ae5c17f25b298b2d7290cd29` | `1766bcae37d189725c1a1305a7724fd9441ebc54` | Record 2025 Silver Delta load in trial workspace |
| `aeea7734d3c926b88b9553b1f383f94e6d569120` | `0438c64b257a3134d1a0f5ed32f9447571a35e2b` | Record final naive and Prophet run (504/504 cells) |
| `266c5f6902c577ae28ee363c8d8a2d1b78729b7e` | `7f0ccda767a5a9751aedb5d28787c9e2a38ca152` | Add release evidence export and final chart scripts |
| `2a5c0e762410a98fea87783dd233208dc3215e7d` | `df27a4bbb716591dc6edec2b03b17560232755ca` | Record final ai_forecast v2 run (252/252 cells, 0 cached) |
| `2441246979e554d8a9fb05ee05faac362df89fd4` | `d72f5361338543f7ea20f2fe7e2520916b302c12` | Combine and independently verify final three-model benchmark |
| `a188d458ad63f30ce191b89827816909eae9fe1d` | `798ffaba6db2cbf0297f24e83cb10e75eed122b4` | Publish-ready README results, claims, data card and validation report; redact host |
| `6ad85ac3d1c868f3921018a33915bf521f39adc8` | `3db784cfb1aa286a54edbca3a636354a5aad211d` | Record repeatability check and release-candidate state |
| `62668840bc1da847a37018915c14434fda9c3217` | `e5c3b70ab7eadfacb15a3edf372731dd28c8ed3d` | Persist final run to Delta, SQL-verify headline, add final dashboard deployer |
| `a7a2ed004c01fbdcba48c026e842aef6ee8e7b34` | `b8c01a5e17f985b7d033b9a2722657555eabc52d` | Verify claims three ways; record Delta persistence and final dashboard |
| `—` | `ed18a08ad385d16508e1fcf27707066d864731d3` | Map rewritten commit SHAs; widen dashboard title |
| `—` | `c9b25ce0d132f72f0c226414bf913b30f5783b96` | Finalize release candidate documentation |
| `—` | `ff697333976b38bc3f38407f9e6e669be884c377` | Record completed history purge |
| `—` | `9335c989199b813df4597d9908b312266f8cf128` | Tidy repository for publication: move design docs, rewrite READMEs, untrack private files |
