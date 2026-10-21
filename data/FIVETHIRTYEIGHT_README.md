# FiveThirtyEight foul-ball data (906 balls, 2019)

`fivethirtyeight_foul_balls.csv` is a byte-for-byte copy of `foul-balls.csv`
from FiveThirtyEight's data repository, retrieved on 2026-10-21 from
<https://raw.githubusercontent.com/fivethirtyeight/data/master/foul-balls/foul-balls.csv>.

- Repository: <https://github.com/fivethirtyeight/data/tree/master/foul-balls>
- Story: *We Watched 906 Foul Balls To Find Out Where The Most Dangerous Ones
  Land* (FiveThirtyEight, July 2019). The live URL now redirects to ABC News;
  a Wayback snapshot dated 2026-03-01 was readable on 2026-10-21.
- License: the repository's README says its data sets are available under the
  Creative Commons Attribution 4.0 International License. This copy is
  redistributed under that license with attribution to FiveThirtyEight.
- Columns, from the upstream README: `matchup`, `game_date`, `type_of_hit`
  (Fly, Ground, Line, Pop Up, Batter hits self), `exit_velocity` (blank if not
  provided), `predicted_zone` (zone estimated by gauging angles), `camera_zone`
  (zone confirmed by footage, blank where no camera followed the ball),
  `used_zone` (the zone the story analysed).

Nothing in this file is model input. It is the observed data the model is
tested against in `VALIDATION.md` (Step 28); the method is fixed in
`VALIDATION_PLAN.md`.
