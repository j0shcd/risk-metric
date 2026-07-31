# Count the MVRV source once

The production model will retain one accurately named MVRV Ratio Proxy and remove the derived `supply_in_profit` and complementary `supply_in_loss` proxies from scoring. All three existing fields originate from the same MVRV ratio and therefore cannot count as independent evidence across model categories. A clearly labeled Derived Profitability View may remain in the explanatory UI because it is intuitive, but it has zero independent weight and must disclose that it is a visualization of the same MVRV source.

## Consequences

- Production score history and registered baselines must be regenerated.
- Old supply fields may be read through a temporary compatibility adapter but are not produced as model components for new releases.
- The canonical internal/public name becomes `mvrv_ratio_z_proxy`, not `mvrv_z_score`.
- A genuinely independent supply-profitability source may be considered later only through the exploratory-to-registered evaluation process and within the project's free-service constraint.
