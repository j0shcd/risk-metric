# Center the product on the DCA Risk Indicator

The DCA Risk Indicator is the product's primary output: a single long-horizon metric for whether approximately the next six months favor accumulation or de-risking. The dashboard, threshold alerts, and explanatory hierarchy will center on this indicator; component and legacy headline indicators move to a secondary explanation page. A separately named Dynamic DCA Strategy may buy, hold cash, and sell (“DCA out”) from indicator thresholds, while a small Scenario Planner lets users compare simple historical strategies. All simulations will share one accounting and execution engine, but user-selected scenarios are illustrative; the Validation Benchmark is the research system used to establish whether the indicator has useful and robust historical skill.

## Considered options

- Making the existing raw cycle-score strategy the product contract would preserve implementation but leave the dashboard and evaluation centered on different metrics.
- Making the current frontend simulator itself canonical would align the UI but conflate a user-configurable scenario with validated model evidence.
- Separating indicator, strategy, planner, and benchmark preserves one primary product metric while giving each use case an explicit evidentiary role.

## Consequences

- The current production Dynamic DCA implementation must be adapted to consume the canonical DCA Risk Indicator or explicitly retained as a non-canonical research reference.
- Fixed DCA is the primary real-world strategy benchmark.
- Component metrics remain visible for transparency but are not peers of the headline product metric.
- Historical simulations must use shared contribution, execution, cost, cash, and return-accounting rules.
