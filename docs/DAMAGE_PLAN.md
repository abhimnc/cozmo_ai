# Damage detection: why it is absent, and what would build it

The output contract asks for per-surface damage regions, concealed-damage flags
and scope line items. The **rules and the scope generator exist and are tested**
(`cozmo demo-damage`); what is missing is the stage that turns an image into a
damage region. This records why, and what building it would actually take, so the
gap is a position rather than an omission.

---

## 1. Open data cannot substitute for the benchmark

The brief is explicit: *"Because we provide no captures, you build the benchmark
set yourself"*, with a specified composition — own device, all three tiers, a
repeatability pair, laser or tape ground truth on everything.

No public dataset satisfies that. Substituting one would answer a different
question, and the composition requirements exist precisely to stop it. Our tape
measurements of the Living room and Hall remain the benchmark's ground truth.

Where open data **is** permitted is as a *model* input: the constraints allow
"any pretrained model, dataset or API with disclosure". That is the route below.

---

## 2. The damage classes are not equally tractable

| Class | Open data | Assessment |
|---|---|---|
| **Cracks** | Good. Several large public crack-image sets exist for concrete and masonry (SDNET2018, CrackForest and similar), plus community sets. | **Tractable.** A crack is a thin high-contrast linear feature — close to the line-segment machinery this pipeline already runs. |
| **Water staining** | Thin. Mostly small community-contributed sets of uneven quality and labelling. | **Hard.** A water stain is a soft-edged discolouration, easily confused with shadow, paintwork, and the warm indoor lighting throughout our captures. |
| **Mould** | Thin, and mostly close-up photography rather than room-scale. | **Hard.** Same problem, plus scale mismatch: our frames view a wall from metres away. |

**The honest consequence:** a detector built in the available time would cover
cracks and little else, which is one damage class. The benchmark requires a room
with **two** classes, so a crack-only detector would not satisfy row 2.14 either.

Licensing on each set needs checking before use — several require a signed
research-use agreement, and that would be disclosed per the constraints.

---

## 3. What building it would take

1. **Source and licence-check** a crack dataset. Half a day, mostly verification.
2. **Adapt a segmentation model** — a small U-Net or a fine-tuned segmentation
   backbone. Cracks are a well-posed binary segmentation problem.
3. **Bridge the domain gap.** Public crack data is overwhelmingly close-up
   photographs of concrete and asphalt. Our frames view painted interior walls
   from two to five metres. That gap is the real work, not the training.
4. **Convert masks to metric regions.** This part we already have: a mask on a
   wall whose distance is known back-projects to an area in m² through the same
   floor-plane geometry that measures the rooms.
5. **Wire to the rules.** Already built. `evaluate()` takes damage regions and
   returns flags; `build()` turns both into scope.

Steps 4 and 5 are done. Steps 1–3 are one to two days.

---

## 4. Why it was not attempted

Two reasons, in order of weight.

**It would have detected nothing.** This is a real, lived-in home with no
significant damage. A crack detector run on the 61 photos would return either
nothing or false positives on grout lines, cable runs and wall junctions — and a
false positive is scored as harshly as a miss.

**Staging damage was declined.** The operator chose not to tape proxy damage to
the walls, which was their call and a reasonable one. Without staged damage there
is no ground truth to score a detector against, so a detector would produce
numbers nobody could check — the confident-garbage failure the brief caps scores
for.

---

## 5. What we would do first, given more time

Not the detector. **Wall identity** — see the technical report's next-steps
section. Knowing which physical wall a measurement belongs to is the single
blocker behind three separate failures: wall assignment for openings, room
placement from measured pose, and the averaging of different walls into one
dimension. Damage detection sits downstream of a pipeline that can already locate
surfaces reliably, and that pipeline does not exist yet.

A damage detector on top of a geometry stage correlating +0.84 with room size
would report damage on the wrong wall a fifth of the time. Fixing the foundation
first is the right order.
