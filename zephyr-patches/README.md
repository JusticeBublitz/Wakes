# zephyr-patches

Local patches to the pinned Zephyr v4.3.1 checkout. These live outside `west`'s
manifest and do **not** survive `west update` — reapply them (`git apply` from
the `zephyr/` checkout root) whenever the Zephyr tree is re-cloned or reset.

- `nordic-cmsis-system-core-clock.patch` — `soc/nordic/Kconfig`'s
  `SOC_FAMILY_NORDIC_NRF` unconditionally selects
  `CMSIS_CORE_HAS_SYSTEM_CORE_CLOCK`, but `modules/cmsis_6/Kconfig` only
  allows that symbol for `SOC_SERIES_IMXRT6XX` (NXP). That makes the symbol
  unreachable for any Nordic build, which Zephyr's `kconfig.py` treats as a
  fatal error on a fresh (non-incremental) configure — this breaks *any*
  from-scratch nRF52 build on this exact Zephyr tag, not just ours (confirmed
  against the stock `samples/hello_world` on `nrf52840dk/nrf52840`). Verified
  against Zephyr's `main` branch on 2026-09-14: both `soc/nordic/Kconfig` and
  `modules/cmsis_6/Kconfig` are unchanged there too, so this is not yet fixed
  upstream. The patch adds a `default y` for the symbol scoped to
  `SOC_FAMILY_NORDIC_NRF`, mirroring the existing `SOC_SERIES_IMXRT6XX` block
  in `soc/nxp/imxrt/imxrt6xx/Kconfig.defconfig`.
