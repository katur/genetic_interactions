Miscellaneous database queries

Get pairwise weak enhancer counts by mutant:

    SELECT E1.worm_strain_id, COUNT(DISTINCT E1.worm_strain_id, E1.id, S1.well, E2.id, S2.well)
    FROM ManualScore AS S1, ManualScore AS S2, Experiment AS E1, Experiment AS E2
    WHERE E1.library_plate_id = E2.library_plate_id
    AND E1.id < E2.id AND S1.experiment_id = E1.id AND S2.experiment_id = E2.id
    AND S1.well = S2.well
    AND E1.worm_strain_id = E2.worm_strain_id
    AND E1.is_junk = 0 AND E2.is_junk = 0
    AND ((S1.score_code_id=12 AND S2.score_code_id=12) OR (S1.score_code_id=16 AND S2.score_code_id=16)
    OR (S1.score_code_id=12 AND S2.score_code_id=16) OR (S1.score_code_id=16 AND S2.score_code_id=12))
    GROUP BY E1.worm_strain_id;


Get strong or medium enhancer counts by mutant:

    SELECT E1.worm_strain_id, COUNT(DISTINCT E1.worm_strain_id, E1.id, S1.well, E2.id, S2.well)
    FROM ManualScore AS S1, ManualScore AS S2, Experiment AS E1, Experiment AS E2
    WHERE E1.library_plate_id = E2.library_plate_id
    AND E1.id < E2.id AND S1.experiment_id = E1.id AND S2.experiment_id = E2.id
    AND S1.well = S2.well
    AND E1.worm_strain_id = E2.worm_strain_id
    AND E1.is_junk = 0 AND E2.is_junk = 0
    AND (S1.score_code_id=13 OR S2.score_code_id=13 OR S1.score_code_id=14 OR S2.score_code_id=14
    OR S1.score_code_id=17 OR S2.score_code_id=17 OR S1.score_code_id=18 OR S2.score_code_id=18)
    GROUP BY E1.worm_strain_id;