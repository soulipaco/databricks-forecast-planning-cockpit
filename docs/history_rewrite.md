# History rewrite: workspace host redaction

On 2026-09-29, at the owner's request before publication, every commit was rewritten to replace the Free Edition workspace URL in `capability_report.md` with `<workspace-host>`. No other file content changed; tree contents at HEAD are identical apart from that file's history.

Evidence files, run IDs (for example `final-native-v2-aeea7734d3c9`) and the freeze manifest (`code_sha` `c5fdacc…`) record **pre-rewrite** commit SHAs. Use this table to find the equivalent commit. Run IDs keep their original SHA prefixes and are not renamed.

| Old SHA | New SHA | Subject |
|---|---|---|
| `6b31de4566dab89950e384ba238231ff05a4605d` | `6b31de4566dab89950e384ba238231ff05a4605d` | Scaffold NYC 311 forecasting benchmark and validate local adapters |
| `c73bb03722d31e2e708abdee002c3e4fa23f8bb3` | `f879b44215d5608621b4848446a731b70f58613f` | Reconcile 2021-2024 NYC aggregates and freeze development series |
| `465aa7ba6c7264bb82be844b8d5f0f47c5d28458` | `1a4fe0b62847e251f511a279d196d0934b14b6c0` | Add bounded real-data adapter smoke runner |
| `d5a1bccfc29c065d7d50ea998f845078fb56151d` | `302ac1af1bb651c3084e514f5f2ea519a358716e` | Record three-series development adapter smoke evidence |
| `5350b2824b0053d8e0a266b78312be4364153083` | `f1d619082077cd40ccef90c01a630e4061a0ae12` | Implement paired evaluation and development champion rules |
| `f2931d741615861bdce9f497ce6ad9624c578e6a` | `8044a9dece3fc5fcdfabcb10ad3ed7e63c9cc3df` | Verify Databricks development Silver deployment |
| `1f7371748da6c9f9100545869624a04df947f97e` | `ba8640e344c2bd56f29e60f3ab74a56234a8b96f` | Record native v2 runtime dependency blocker |
| `3986bbd7d7421ea65eab47a4df2da3e41122e076` | `de2da91201c9bee7e8ac15c09e89e77572e882ad` | Add bounded two-origin development slice runner |
| `84b6ec67315f3657474cba27467f1ba9ac501a61` | `d851df2c245265db9cdb1f60914d787881144098` | Record two-origin local development slice |
| `2e84df4ed954b82f93a90b4b9fc32ebe573ca006` | `ea4ddc128bf4654950fd6c01631bea7ecff2c405` | Deploy and verify serving views |
| `7791d34f5b5a7d052e094cc8d9df70fe9d8b056e` | `afa28e5e2f2e7b6b7462ef7bfc5c2e439a2717be` | Create and verify unpublished development dashboard draft |
| `df7bc516941af31ced5d44dd77ebedc6ba9f5718` | `83426ce9e87b6e64727149fc698bf28e88335884` | Load verified source and series lineage metadata |
| `44e8dcb62a93647b7ff0ec186610e821dd339544` | `0500aa664fc8b1a7b2bd1ce4b809b7217c950c65` | Preserve hashed JSON payload line endings |
| `e51521df538bb68ef2bed42433d00af4724acf53` | `589e01ca4fe807886ad572acef12789bf3913644` | Serve reconciled development data quality |
| `d47dda59a5aa83a4c97324612b741cdd85954354` | `bae4321f795cb977fa8e064736356766a7ee7575` | Refresh next milestone after data-quality deployment |
| `31ee879fa73d0f4e7e81c88fa35ad481d8f96afb` | `7173a78e4168ee6a1429d880f7ecf1182b4f6e79` | Persist development smoke and extend readiness evidence |
| `66ee77ad9d8770f68046c49d02c7767a9a7d3971` | `a2dbf97ee8df03ca1df10a93dfcf56cdb0073713` | Record bounded Prophet development tuning smoke |
| `3afb8b112a160c75db2c173cfdb564af26702fea` | `fc75eda8ae3abc16bf191ddf0493ee1b4060daa1` | Record Free Edition v2 access blocker |
| `30862cc33ddc821e88724a68157184fa2583cfcb` | `48068dd35113675e3cc2571813054046f507c4d4` | Complete Prophet tuning and prepare two-model development run |
| `0d96d7e8d834fec2c66fc855a818c52e8418ed75` | `681c0f4efbfe8c43ff91f5ff5e669ae74d0149ea` | Verify and present 2024 two-model development results |
| `7220f6bb416b2b189ded2ea24a0bd938ad0289e4` | `92d590a9f139b1a2fe6794545e3c83368582d10d` | Add freeze gate and deploy development jobs as a bundle |
| `059bfe7b4f93de2f9a9fcf7e39387fce2a60d5da` | `6a7ef3f8e0d7f393090a960fef3f3930247d7571` | Independently re-verify ai_forecast v2 blocker |
| `52563c6470ea9319206788acbed36539f1714d2d` | `7dc6309eaa3d4e784ec306c71edfc525fd3aabb5` | Record serverless egress probe; LinkedIn route exhausted for v2 |
| `60e97c09e4cfb23255c98c7e6191c19e5268c3f1` | `3b68224b5e6e2c66197348326b38145fe61c11d7` | Record v2 smoke failure in trial workspace |
| `d6ff569be4b03825ecd56ee4fcf83a863f08abad` | `934206d54121dfd1db6990f5417d13005ee8b10b` | Record trial v2 attempts after networking preview |
| `378e4477604ad5e85acb1bb8f80c56ce3b1fb44b` | `0a6430afccde7d6418266982973f2b04e9aa2b55` | Verify ai_forecast v2 in trial workspace; request inclusive horizon |
| `fe9f8b2e98fabacbfec25b525aa2673cca68c472` | `4e6b34845f87f95d1d6b09c9139c3a004aaf3a4d` | Add v2 development runner and trial workspace Silver load |
| `f640d1928e958c4f6e1d7b9fdc30690705adf491` | `549d811d063895f779c5e0ac4c2d9b2142dffaf7` | Record one-series v2 development pilot |
| `c5fdacc0d163290b7e0a23a301848a2534a2b6df` | `f57754f06da299da0590594656f217ea3cc44e67` | Complete three-model 2024 development grid and register deviations |
| `42ce7907ea9ed4065f0670b913a7949f9c1dcc78` | `883dde2a7107f63fa239d3387e71c92f5e660dfe` | Freeze benchmark protocol v1.0 |
| `76e1857a3370adf134486da8ba030e529317c2d5` | `30e43be1b7786d6f053b2398b360a953bb982134` | Add frozen final benchmark stages and 2021-2025 Silver materializer |
| `31b8abeb72deb81d1317665e67e2d83a5b2cfef3` | `430e90274dc073089a8ebbdff8b1ce8fc11511ff` | Add 2025 evaluation snapshot and 2021-2025 Silver after freeze |
| `652b3f66baac4cef0ac5a6d6e39d77436928cb39` | `4a2e270fc9c1ec17fa3aa84b72927db389d0a41a` | Tie final runs to development tuning lineage; parameterize Silver load |
| `10cc5e39cfde2b846eca6ecd2454a51490b029bb` | `ef7b084bda829bda85b839d870cef5feb3d05c82` | Fix final lineage test expectation |
| `80e0a12bdce76589ae5c17f25b298b2d7290cd29` | `dcd64be72a3ada03b8fa7373e5799ea651123216` | Record 2025 Silver Delta load in trial workspace |
| `aeea7734d3c926b88b9553b1f383f94e6d569120` | `3ea2589793d49811988b907ba4c8a105e4e91dc4` | Record final naive and Prophet run (504/504 cells) |
| `266c5f6902c577ae28ee363c8d8a2d1b78729b7e` | `b60b0ef8150255c23e83b4d393debf7f58335257` | Add release evidence export and final chart scripts |
| `2a5c0e762410a98fea87783dd233208dc3215e7d` | `0177a619380fdccd77bc9d1413cd5680fa1b83f8` | Record final ai_forecast v2 run (252/252 cells, 0 cached) |
| `2441246979e554d8a9fb05ee05faac362df89fd4` | `3831bfb3d66367324ae034ac5fa67fca92ecc7b3` | Combine and independently verify final three-model benchmark |
| `a188d458ad63f30ce191b89827816909eae9fe1d` | `4bff8d5ec42f3525a969f658de2487f8f14df9a9` | Publish-ready README results, claims, data card and validation report; redact host |
| `6ad85ac3d1c868f3921018a33915bf521f39adc8` | `444dfd8d5093272e79ee95eddde9753b3f5911ab` | Record repeatability check and release-candidate state |
| `62668840bc1da847a37018915c14434fda9c3217` | `e3bb85c1b5a74a0d3e351053201b54089b343c9f` | Persist final run to Delta, SQL-verify headline, add final dashboard deployer |
| `a7a2ed004c01fbdcba48c026e842aef6ee8e7b34` | `7892a0e70c553e3ba03c77167a9e38d4b5ac8b97` | Verify claims three ways; record Delta persistence and final dashboard |
