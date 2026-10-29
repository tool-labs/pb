-- Minimal stand-in for the parts of the CentralAuth replica (centralauth_p) and of
-- meta_p.wiki that pb uses. Column types follow the replica views.

CREATE TABLE `localuser` (
  `lu_wiki` varbinary(255) NOT NULL,
  `lu_name` varbinary(255) NOT NULL,
  `lu_local_id` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`lu_wiki`, `lu_name`)
) ENGINE=InnoDB DEFAULT CHARSET=binary;

CREATE TABLE `globaluser` (
  `gu_id` int(11) NOT NULL AUTO_INCREMENT,
  `gu_name` varbinary(255) DEFAULT NULL,
  `gu_home_db` varbinary(255) DEFAULT NULL,
  PRIMARY KEY (`gu_id`),
  UNIQUE KEY `gu_name` (`gu_name`)
) ENGINE=InnoDB DEFAULT CHARSET=binary;

-- meta_p.wiki
CREATE TABLE `wiki` (
  `dbname` varchar(32) NOT NULL,
  `url` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`dbname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
