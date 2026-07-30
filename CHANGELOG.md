# Changelog

All notable changes to this project will be documented in this file.
## [0.8.7](https://github.com/satyaborg/blurt/releases/tag/v0.8.7) — 2026-07-30

### Bug fixes

- fix: prioritize coding hints over file names ([09d3331](https://github.com/satyaborg/blurt/commit/09d3331bcaeac8e9940abcbf7704957475a8837e))
## [0.8.6](https://github.com/satyaborg/blurt/releases/tag/v0.8.6) — 2026-07-30

### Bug fixes

- fix: silence pipx home path warning ([a9c9e90](https://github.com/satyaborg/blurt/commit/a9c9e90a128066e319117611b9f25f591504714d))
- fix: delay Bluetooth media resume ([6b917f3](https://github.com/satyaborg/blurt/commit/6b917f3fd93ff4b024300ed48de54d6c8f8dd758))
- fix: transfer paused media ownership ([bcef2ff](https://github.com/satyaborg/blurt/commit/bcef2ffd6234c0bbe47a6075905dca3e92abf29c))
- fix: respect disabled media pause setting ([c59b7ec](https://github.com/satyaborg/blurt/commit/c59b7ec53c320f091719ad8ba8d8a28153f87eb9))

### Other

- changelog v0.8.6 ([e2b1495](https://github.com/satyaborg/blurt/commit/e2b1495ec19bc04b49975d59ecc944e7a1ca05e3))
## [0.8.5](https://github.com/satyaborg/blurt/releases/tag/v0.8.5) — 2026-07-30

### Bug fixes

- fix: reduce transcription latency ([dd29f25](https://github.com/satyaborg/blurt/commit/dd29f25f34a1747d1523d858ad9843f37221cb4a))

### Other

- changelog v0.8.5 ([1646aaa](https://github.com/satyaborg/blurt/commit/1646aaa5aa351e7bdfdbec5fe2fc05e6cf9e9e54))
## [0.8.4](https://github.com/satyaborg/blurt/releases/tag/v0.8.4) — 2026-07-30

### Features

- Add fast/accurate model mode switching and migrate config to JSON ([40ff15e](https://github.com/satyaborg/blurt/commit/40ff15e385e7e4fed37f0d0020edf2e746fe3793))

### Other

- feat!: toggle recording with shortcut presses ([11ce0d1](https://github.com/satyaborg/blurt/commit/11ce0d1f1df75d62fde30ac8c9552dbd8dc35e75))
- changelog v0.8.4 ([f9e3d6b](https://github.com/satyaborg/blurt/commit/f9e3d6bc7d73cef4892a363440d8615dedefb7b1))
## [0.8.3](https://github.com/satyaborg/blurt/releases/tag/v0.8.3) — 2026-04-07

### Bug fixes

- Fix audio clipping and start/stop race in recording flow ([4a2a9c1](https://github.com/satyaborg/blurt/commit/4a2a9c18078f332a1607d2d1fbf4257b527e66cb))

### Other

- changelog v0.8.3 ([108d966](https://github.com/satyaborg/blurt/commit/108d966fcca49588277f8254e9b84e0e11332f3c))
## [0.8.2](https://github.com/satyaborg/blurt/releases/tag/v0.8.2) — 2026-03-13

### Bug fixes

- Fix release.sh tap update race condition and dead code ([6fcd1f6](https://github.com/satyaborg/blurt/commit/6fcd1f63338e9887b0b3211fa631952a2d5fc782))

### Other

- changelog v0.8.2 ([1335075](https://github.com/satyaborg/blurt/commit/13350753cbe716d46c22587cbf130f3a2c271c3b))
## [0.8.1](https://github.com/satyaborg/blurt/releases/tag/v0.8.1) — 2026-03-13

### Features

- Add Homebrew tap as primary install method ([a9ac40f](https://github.com/satyaborg/blurt/commit/a9ac40fc131d194727a618325a1bd2100bf6310e))

### Other

- changelog v0.8.1 ([bb7a615](https://github.com/satyaborg/blurt/commit/bb7a6156e913f3ca4f5eafb2b2a9ab0ca307f942))
## [0.8.0](https://github.com/satyaborg/blurt/releases/tag/v0.8.0) — 2026-03-13

### Bug fixes

- Fix test_save_config missing AUDIO_DIR monkeypatch ([d81a76d](https://github.com/satyaborg/blurt/commit/d81a76deb1a529f0dfb0c46d47e393180b9a35a5))

### Other

- feat: pause/resume media during recording ([9204f0d](https://github.com/satyaborg/blurt/commit/9204f0d0ba6cfcf46f86bcbae9d3a5398e5749c1))
- Clean up media pause feature and enable by default ([d926c3b](https://github.com/satyaborg/blurt/commit/d926c3b8f41d85294b38030b3f74e229f8a6e158))
- changelog v0.8.0 ([3f8389d](https://github.com/satyaborg/blurt/commit/3f8389d3020cf86a793694efa3baad853e83bc3a))
## [0.7.7](https://github.com/satyaborg/blurt/releases/tag/v0.7.7) — 2026-03-13

### Features

- Add ready sound chime on model load ([b01a5f7](https://github.com/satyaborg/blurt/commit/b01a5f78012f86daaf8e181ce6d1463f7c28a843))

### Other

- changelog v0.7.7 ([57fcb79](https://github.com/satyaborg/blurt/commit/57fcb79aef4299891eabf54dc31e9d62f3150e44))
## [0.7.6](https://github.com/satyaborg/blurt/releases/tag/v0.7.6) — 2026-03-12

### Other

- Detect vocab prompt echo as hallucination on silent recordings ([3263df6](https://github.com/satyaborg/blurt/commit/3263df60cb6e88ed931fb3b48cedb951427c500d))
- changelog v0.7.6 ([036909a](https://github.com/satyaborg/blurt/commit/036909ae4c2771eb992b0da09f045862872450ec))
## [0.7.4](https://github.com/satyaborg/blurt/releases/tag/v0.7.4) — 2026-03-09

### Features

- Add periodic model keep-alive to prevent cold starts after idle ([716dc38](https://github.com/satyaborg/blurt/commit/716dc3806593524afc097cff14448ac7445ded2d))

### Other

- changelog v0.7.3 ([ba4bd9c](https://github.com/satyaborg/blurt/commit/ba4bd9c81f944505a3366484724913b4c53726e2))
- changelog v0.7.4 ([821f731](https://github.com/satyaborg/blurt/commit/821f7317fd7e7402258e1686d736fc4ee251cffb))
## [0.7.2](https://github.com/satyaborg/blurt/releases/tag/v0.7.2) — 2026-03-09

### Bug fixes

- Fix doctor portaudio check for DeviceList type ([7d5152b](https://github.com/satyaborg/blurt/commit/7d5152b436becff04b69272b2ff3ebb0a18b9354))

### Other

- changelog v0.7.2 ([e3f384f](https://github.com/satyaborg/blurt/commit/e3f384f481d7243192a60650831471351e574bc6))
## [0.7.1](https://github.com/satyaborg/blurt/releases/tag/v0.7.1) — 2026-03-09

### Changes

- Remove unused sounds directory ([8e1db44](https://github.com/satyaborg/blurt/commit/8e1db44d454a3665d4c784c4c5e73bf90abe97bc))
- Remove unused THEMES variable ([3e5e728](https://github.com/satyaborg/blurt/commit/3e5e728d0e375f93f913143e10cc2c681cbf564c))

### Other

- changelog v0.7.1 ([f8ec340](https://github.com/satyaborg/blurt/commit/f8ec340a6cadfa149a28ff71b08529fa27eee7ba))
## [0.7.0](https://github.com/satyaborg/blurt/releases/tag/v0.7.0) — 2026-03-09

### Features

- Add reliability, multi-language, VAD, doctor; remove sounds ([e66cfbe](https://github.com/satyaborg/blurt/commit/e66cfbe36c3745322b7ed90c0c11e255f558462d))

### Other

- changelog v0.6.5 ([d07c1a8](https://github.com/satyaborg/blurt/commit/d07c1a8ed20981d7776b1931ae50eb55546728a3))
- changelog v0.7.0 ([ccf04c7](https://github.com/satyaborg/blurt/commit/ccf04c79d9a0cd55be5dbb82da66725367bb4175))
## [0.6.4](https://github.com/satyaborg/blurt/releases/tag/v0.6.4) — 2026-03-09

### Changes

- Remove investigation doc from tracked files ([38c54b4](https://github.com/satyaborg/blurt/commit/38c54b4befcb7035870d3e8c73432d05784177cf))

### Features

- Add macOS Tahoe compatibility investigation ([6d86c77](https://github.com/satyaborg/blurt/commit/6d86c77f4c31ae471b1f5a92911708f576b5536e))

### Other

- Improve reliability on macOS Tahoe while keeping backward compat ([aa8982d](https://github.com/satyaborg/blurt/commit/aa8982d07ba26c6dd8b43b1b6fe13a0b808af2e6))
- changelog v0.6.4 ([855f9a7](https://github.com/satyaborg/blurt/commit/855f9a70039a943b21bf39b83c5eafd55cf78bc5))
## [0.6.2](https://github.com/satyaborg/blurt/releases/tag/v0.6.2) — 2026-03-03

### Bug fixes

- Fix duplicate PyPI publish failures with skip-existing ([c052c8a](https://github.com/satyaborg/blurt/commit/c052c8ad9409840e289e2c26bef171be39edc16c))

### Other

- changelog v0.6.2 ([39e8050](https://github.com/satyaborg/blurt/commit/39e805009a8408e26e4bbd9eeb936d32232e7ccf))
## [0.6.1](https://github.com/satyaborg/blurt/releases/tag/v0.6.1) — 2026-03-03

### Other

- Speed up sound feedback and fix model pre-warm kwargs ([bd79a9b](https://github.com/satyaborg/blurt/commit/bd79a9b55ecbd58f776d43019c9b4cecd8b7fa10))
- changelog v0.6.1 ([dea7201](https://github.com/satyaborg/blurt/commit/dea7201256f1bfb5c45b60e38e82e9c3fb3fd0fb))
## [0.5.5](https://github.com/satyaborg/blurt/releases/tag/v0.5.5) — 2026-02-20

### Features

- add precommit hook ([1fac32b](https://github.com/satyaborg/blurt/commit/1fac32b5865ea9cd6b919ac40857fae0a6d36c85))

### Other

- changelog v0.5.5 ([6d81f77](https://github.com/satyaborg/blurt/commit/6d81f77f7f2dc2877be1c681142e777e443c8cb0))
## [0.5.4](https://github.com/satyaborg/blurt/releases/tag/v0.5.4) — 2026-02-20

### Other

- improve docs on file indexing ([0735196](https://github.com/satyaborg/blurt/commit/07351965006faa3c69cc9098ba3d2316fda6e6ed))
- changelog v0.5.4 ([d43a1b3](https://github.com/satyaborg/blurt/commit/d43a1b32c1a9fd873363fdb90c18939f7bab9211))
## [0.5.3](https://github.com/satyaborg/blurt/releases/tag/v0.5.3) — 2026-02-19

### Features

- add update alias ([ce4a569](https://github.com/satyaborg/blurt/commit/ce4a5690119ee86ae446599db2504dce2668e018))

### Other

- changelog v0.5.3 ([788025e](https://github.com/satyaborg/blurt/commit/788025ef02f9f45da29e3e18f3035bdd9c1ac4b8))
## [0.5.2](https://github.com/satyaborg/blurt/releases/tag/v0.5.2) — 2026-02-19

### Features

- add auto update check ([21c61e3](https://github.com/satyaborg/blurt/commit/21c61e3bf8e97720909e5981f9f50a94c38e7732))

### Other

- changelog v0.5.2 ([175fa4e](https://github.com/satyaborg/blurt/commit/175fa4e6cf554275d727dbd1aebf474a79c1a2cc))
## [0.5.1](https://github.com/satyaborg/blurt/releases/tag/v0.5.1) — 2026-02-19

### Bug fixes

- fix relative @file path and trailing whitespace ([2a96287](https://github.com/satyaborg/blurt/commit/2a962871e86b9b7f7d6798076237f63bc13d1b40))

### Other

- changelog v0.5.1 ([4be90e4](https://github.com/satyaborg/blurt/commit/4be90e4350c83d6903eee4bc318dc1436f61ef8e))
## [0.5.0](https://github.com/satyaborg/blurt/releases/tag/v0.5.0) — 2026-02-18

### Features

- add auto filepath resolution ([946751f](https://github.com/satyaborg/blurt/commit/946751f193bc32cbc9b9e9cc8bcc821fe86ddcea))

### Other

- changelog v0.5.0 ([6a56113](https://github.com/satyaborg/blurt/commit/6a56113a0142a91e3c800970f4c8c5d673cdd436))
## [0.4.4](https://github.com/satyaborg/blurt/releases/tag/v0.4.4) — 2026-02-18

### Changes

- mod readme ([b301a24](https://github.com/satyaborg/blurt/commit/b301a24fd6a63363ffd031e21eedfbf69139bbef))

### Features

- add logo ([f0dd38d](https://github.com/satyaborg/blurt/commit/f0dd38d5aeb0729e1ac109147aa2bce1bc176a8d))

### Other

- changelog v0.4.4 ([eb115d7](https://github.com/satyaborg/blurt/commit/eb115d73c2ede04cab1b0193107d947ed5e57011))
## [0.4.3](https://github.com/satyaborg/blurt/releases/tag/v0.4.3) — 2026-02-18

### Changes

- update documentation ([9a635e3](https://github.com/satyaborg/blurt/commit/9a635e39c9d7b546f365299971ed54e1bf0d965e))

### Other

- changelog v0.4.3 ([9a77f07](https://github.com/satyaborg/blurt/commit/9a77f0716831f97f40f09f7cc475568c717fcecf))
## [0.4.2](https://github.com/satyaborg/blurt/releases/tag/v0.4.2) — 2026-02-18

### Changes

- update README.md, AGENTS.md ([0889f9d](https://github.com/satyaborg/blurt/commit/0889f9da6739db5ec3be6e3aeae085a2c9db6219))

### Other

- changelog v0.4.2 ([4b89f5c](https://github.com/satyaborg/blurt/commit/4b89f5c47258d6e3ecdd51cd5b140f2672e5eee0))
## [0.4.1](https://github.com/satyaborg/blurt/releases/tag/v0.4.1) — 2026-02-18

### Features

- add upgrade cmd ([5b7e5ff](https://github.com/satyaborg/blurt/commit/5b7e5ffc845a43d0a08d311f02f6644ad2a0e1d2))

### Other

- changelog v0.4.1 ([7522638](https://github.com/satyaborg/blurt/commit/7522638c2c0e6f9087d50f1e6d1262cb7a8bcccb))
## [0.3.9](https://github.com/satyaborg/blurt/releases/tag/v0.3.9) — 2026-02-18

### Bug fixes

- fix source audio switch ([38d1116](https://github.com/satyaborg/blurt/commit/38d1116ff6784f691e4f54e02f8eeaa7eba0ae5d))

### Other

- changelog v0.3.9 ([8b2ea68](https://github.com/satyaborg/blurt/commit/8b2ea680f7130afeae12734858859feb5a3e7845))
## [0.3.8](https://github.com/satyaborg/blurt/releases/tag/v0.3.8) — 2026-02-18

### Other

- display relative paths ([416405b](https://github.com/satyaborg/blurt/commit/416405b9860c8869122b3c1efaf2daa4ef689ca5))
- changelog v0.3.8 ([12a3154](https://github.com/satyaborg/blurt/commit/12a3154c77183f81a9c229482c7086077d70ef44))
## [0.3.7](https://github.com/satyaborg/blurt/releases/tag/v0.3.7) — 2026-02-17

### Bug fixes

- fix typo ([df34ba2](https://github.com/satyaborg/blurt/commit/df34ba222f04fa77cedbd2f1b028cc7b4acb02b4))

### Other

- changelog v0.3.7 ([b6eb888](https://github.com/satyaborg/blurt/commit/b6eb888123ea064c05f13c73efd0448453c85f8a))
## [0.3.6](https://github.com/satyaborg/blurt/releases/tag/v0.3.6) — 2026-02-17

### Bug fixes

- fix f-string linting ([beff3e3](https://github.com/satyaborg/blurt/commit/beff3e3158466eb98f9cb7ca2ee340a460b2183c))

### Other

- changelog v0.3.6 ([d8700b8](https://github.com/satyaborg/blurt/commit/d8700b81e7864ba22e93367c06f4799d8b0499c9))
## [0.3.5](https://github.com/satyaborg/blurt/releases/tag/v0.3.5) — 2026-02-17

### Changes

- mod vocab args ([e7c15ac](https://github.com/satyaborg/blurt/commit/e7c15ac308a058d932527a8af3df92aef7c5387e))

### Other

- changelog v0.3.5 ([7c7fd6c](https://github.com/satyaborg/blurt/commit/7c7fd6c43449e95470d92200441e9858c35ba557))
## [0.3.4](https://github.com/satyaborg/blurt/releases/tag/v0.3.4) — 2026-02-15

### Changes

- update demo.gif ([d36c15c](https://github.com/satyaborg/blurt/commit/d36c15c0869cb645de7ee362780d824f2b44aa1b))

### Other

- changelog v0.3.4 ([9b22360](https://github.com/satyaborg/blurt/commit/9b223600edaa3e3f86825d9ecc460c6fdbed98af))
## [0.3.3](https://github.com/satyaborg/blurt/releases/tag/v0.3.3) — 2026-02-14

### Changes

- update readme ([b2ffbc0](https://github.com/satyaborg/blurt/commit/b2ffbc058998dda0655fe868a4ab11e3f717ffea))

### Other

- changelog v0.3.3 ([24d6b00](https://github.com/satyaborg/blurt/commit/24d6b000c36d718033d8b766209ec337e3903454))
## [0.3.2](https://github.com/satyaborg/blurt/releases/tag/v0.3.2) — 2026-02-14

### Features

- add vocab, refactor ([fbf8537](https://github.com/satyaborg/blurt/commit/fbf853774051183c0a4e5493316fce2056b2a910))

### Other

- changelog v0.3.2 ([dcc6835](https://github.com/satyaborg/blurt/commit/dcc6835b51b18b6ad179a50b6b6943fa6e64ea69))
## [0.3.1](https://github.com/satyaborg/blurt/releases/tag/v0.3.1) — 2026-02-14

### Features

- add vocab, keyword boosting and auto-correction ([9d78b6c](https://github.com/satyaborg/blurt/commit/9d78b6cba0fc7a9b6bd5fb8a19400a97e9a818a6))

### Other

- changelog v0.4.0 ([5e7fd01](https://github.com/satyaborg/blurt/commit/5e7fd01d5148da21e4c89ea784316df284017bda))
- revert auto-correction ([31f80b5](https://github.com/satyaborg/blurt/commit/31f80b57bf0e5fc3bd3adcff710f32e067617f35))
- changelog v0.3.1 ([5879f6e](https://github.com/satyaborg/blurt/commit/5879f6ef3abec33d8acf462cf48dfc8a2afe7553))
## [0.3.0](https://github.com/satyaborg/blurt/releases/tag/v0.3.0) — 2026-02-14

### Features

- add tests ([eeccc96](https://github.com/satyaborg/blurt/commit/eeccc966ef500d92a8b10750e14eb2e66160960e))

### Other

- changelog v0.3.0 ([bbab970](https://github.com/satyaborg/blurt/commit/bbab970a30cdfab05f7d086845dbdbdbced9136a))
## [0.2.9](https://github.com/satyaborg/blurt/releases/tag/v0.2.9) — 2026-02-14

### Other

- show download progress ([771f7ac](https://github.com/satyaborg/blurt/commit/771f7ac1e7e9b4fc8b1285e2c956f96bd6d899fd))
- changelog v0.2.9 ([81ccaf8](https://github.com/satyaborg/blurt/commit/81ccaf8ea62f3ab0347a9a0eada86e268ebb4051))
## [0.2.8](https://github.com/satyaborg/blurt/releases/tag/v0.2.8) — 2026-02-14

### Bug fixes

- fix global esc ([1b81b94](https://github.com/satyaborg/blurt/commit/1b81b949fe158cededbf54a2baea3f01489e429d))
- fix clipboard ([d879107](https://github.com/satyaborg/blurt/commit/d87910708366c7ff9b97932e58e0e46b8d2fb841))
- fix truncation ([25d8453](https://github.com/satyaborg/blurt/commit/25d8453bf135240fe9ff7076bc10dfde0d5a155b))

### Changes

- rename hotkey -> shortcut ([b43e791](https://github.com/satyaborg/blurt/commit/b43e791bb2dc32abed0adcf5c4e9ca0e1f90a62e))

### Features

- add rich table view -log ([5712fb5](https://github.com/satyaborg/blurt/commit/5712fb5285b347335381009b61c30b23c6953f14))

### Other

- changelog v0.2.8 ([fbbe973](https://github.com/satyaborg/blurt/commit/fbbe9730a95d0e208c340c6774a43f54e81a7fc7))
## [0.2.7](https://github.com/satyaborg/blurt/releases/tag/v0.2.7) — 2026-02-13

### Changes

- mod toml ([cfb8e3a](https://github.com/satyaborg/blurt/commit/cfb8e3a412e9c8d7c4552a70108a9c51553e4c0e))
## [0.2.6](https://github.com/satyaborg/blurt/releases/tag/v0.2.6) — 2026-02-13

### Changes

- mod path ([c6b6e39](https://github.com/satyaborg/blurt/commit/c6b6e39cc05105f3e9b1f2e0cdb43d8c08e1da7a))
## [0.2.4](https://github.com/satyaborg/blurt/releases/tag/v0.2.4) — 2026-02-13

### Features

- add gif ([275f19a](https://github.com/satyaborg/blurt/commit/275f19a8514c2c08b783ede76edbd77fd07db0b0))
## [0.2.3](https://github.com/satyaborg/blurt/releases/tag/v0.2.3) — 2026-02-13

### Features

- add demo ([5de2898](https://github.com/satyaborg/blurt/commit/5de2898998c6f8d3ea15a282f6408fa4919a2ccf))
## [0.2.2](https://github.com/satyaborg/blurt/releases/tag/v0.2.2) — 2026-02-13

### Features

- add upgrade command ([39d4e4b](https://github.com/satyaborg/blurt/commit/39d4e4ba2f9b79bfd56eb938682c077b1d162092))
## [0.2.1](https://github.com/satyaborg/blurt/releases/tag/v0.2.1) — 2026-02-13

### Changes

- update readme ([a3d057a](https://github.com/satyaborg/blurt/commit/a3d057a1da2b9865e03057a0d508e615f01735b1))
## [0.2.0](https://github.com/satyaborg/blurt/releases/tag/v0.2.0) — 2026-02-13

### Bug fixes

- fix docstrings ([b58605f](https://github.com/satyaborg/blurt/commit/b58605f1bd4a08bbe2f7487d762f4f4be5f58207))

### Changes

- bump version ([49e8f9d](https://github.com/satyaborg/blurt/commit/49e8f9d54b0385bfdcad1bff5fbf0491dab71627))
- remove brew ([1f8f438](https://github.com/satyaborg/blurt/commit/1f8f43846cb3f006af677c8717b6b7b6765294d3))

### Features

- add pypi release workflow ([4ec51dd](https://github.com/satyaborg/blurt/commit/4ec51ddf1dd54cf30fddb3245d96cfa0eb0237c1))

### Other

- initial commit ([3d8f2ec](https://github.com/satyaborg/blurt/commit/3d8f2ec487c85207d9bd2335b1d5615933c3e3ed))
