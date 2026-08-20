CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
FOR (c:Concept)
REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT topic_id_unique IF NOT EXISTS
FOR (t:Topic)
REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT resource_id_unique IF NOT EXISTS
FOR (r:Resource)
REQUIRE r.id IS UNIQUE;

CREATE INDEX concept_name_index IF NOT EXISTS
FOR (c:Concept)
ON (c.name);

