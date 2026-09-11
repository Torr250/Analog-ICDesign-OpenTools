# SKY130

[PDK Documentation](https://skywater-pdk.readthedocs.io/en/main/)  
[PDK GitHub](https://github.com/google/skywater-pdk)

## Related presentation material 
[IEEE SSCS Chipathon, July 25, 2024: Transistor sizing basics](https://docs.google.com/presentation/d/1CmZlJf_GPc-H4LRFmhwvaIzZadMvDUaG/present?slide=id.p1)  
[IEEE SSCS Chipathon, August 1, 2024: Sizing a 5T OTA](https://docs.google.com/presentation/d/1CmM5N6-I9DX7aFC9SWwOze7dk5jMOrbj/present?slide=id.p1)

## Modeling issues to be aware of
* Based on the $g_m/I_D$ versus $V_{GS}$ curves, the pfet models look non-physical in moderate and weak inversion. These models should probably not be used for designs with $V_{GS}-V_t < 150 mV$.
* The pfet_01v8 model has unrealistic intrinsic gain ($g_m/g_{ds}$) for long channels (e.g., ~1000 for $L=3\mu m$)
* The fringe capacitances of the pfets (cgsov, cgdov) are on the order of 20-50 $aF/\mu m$. This is unrealistically small.
