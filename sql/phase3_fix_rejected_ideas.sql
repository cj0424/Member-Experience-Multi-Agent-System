-- Phase 3 batch: corrects what was saved in week 2.
-- 1) Rejected ideas: the old method saved options the owner KEPT as "rejected".
--    These are the real rejections and postponements from the owner's feedback.
-- 2) OBS-007 (beginner groups full, people asking for places) was tagged as praise
--    of the teachers; it's unmet demand, so it moves to the new topic plazas_clases.
-- Each update only touches the row it names.

update public.patterns
set rejected_ideas =
'- Descartado: Repintar y optimizar las plazas del aparcamiento (motivo: no quiero obras ahora)
- Pospuesto: Acuerdo de aparcamiento con un negocio cercano (motivo: más adelante)'
where id = 2 and pattern_name like 'Aparcamiento%';

update public.patterns
set rejected_ideas =
'- Descartado: Redistribuir la arena solo una vez por semana (motivo: me parece poco)
- Descartado: Apuntar el cepillado en la libreta de incidencias (motivo: esa libreta es para problemas)'
where id = 3 and pattern_name like 'Acumulación de arena%';

update public.patterns
set rejected_ideas =
'- Pospuesto: Ventiladores industriales portátiles (motivo: solo si abrir los portones no basta)
- Pospuesto: Enfriadores evaporativos o aislamiento del tejado (motivo: lo miramos en primavera, que ahora viene el frío)'
where id = 5 and pattern_name like 'Calor en la nave%';

update public.evidence_tags
set topic = 'plazas_clases', polarity = 'queja'
where evidence_id = 'OBS-007' and topic = 'clases_profesores' and polarity = 'elogio';
