# Overnight data-quality loop, November 14–15, 2026

One line per run: time, problem found, fix, files changed.

- 2026-11-14 02:17: checked the 186 presumed-closed records that still have a website against the addresses on those sites (check_sites functions); 4 matched. Restored Vanadco Signs (site lists 10625 State Road 10, Argos) and Jones Enterprise as NRP Jones at 302 Philadelphia St, La Porte (its site's address); kept Atlas Chem-Milling (building for sale 2025) and Truth Publishing (not a manufacturer) off the map. Files: companies/vanadco-signs-inc--argos--10625.toml, companies/jones-enterprise-inc--la-porte--210.toml
- 2026-11-14 02:24: St. Joe Tool's plant at 11521 Red Arrow Highway was on the map twice, as HIFLD's Bridgman record and its 2025 OSHA filing under the postal town Sawyer. Removed the HIFLD copy as a duplicate; check_consistency.py now also flags the same street address filed under another town within 1 km (only this pair region-wide). Files: companies/st-joe-tool-co--bridgman--11521.toml, scripts/check_consistency.py
