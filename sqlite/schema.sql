create table s_file(
    file_id INTEGER PRIMARY KEY,
    parent_id INTEGER default NULL,
    name,
    content BLOB DEFAULT NULL,
    owner_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    read_owner BOOLEAN not null default 1,
    write_owner BOOLEAN not null default 1,
    execute_owner BOOLEAN not null default 1,
    read_group BOOLEAN not null default 1,
    write_group BOOLEAN not null default 0,
    execute_group BOOLEAN not null default 1,
    read_other BOOLEAN not null default 1,
    write_other BOOLEAN not null default 0,
    execute_other BOOLEAN not null default 1
);

create table s_user( uid INTEGER PRIMARY KEY, 
                   name NOT NULL, password NOT NULL);

create table s_group( gid INTEGER PRIMARY KEY, name NOT NULL);

create table s_user_in_group ( uid INTEGER NOT NULL, 
                             gid INTEGER NOT NULL);



create view if not exists user_rights as
select u.uid,f.file_id,
case 
  when f.owner_id = u.uid then max(f.read_owner)
  when u.uid = uig.uid then max(f.read_group) else max(f.read_other) end as can_read,
case 
  when f.owner_id = u.uid then max(f.write_owner)
  when u.uid = uig.uid then max(f.write_group) else max(f.write_other) end as can_write,
case 
  when f.owner_id = u.uid then max(f.execute_owner)
  when u.uid = uig.uid then max(f.execute_group) else max(f.execute_other) end as can_execute
      from s_user u,s_file f left join s_user_in_group uig on f.group_id = uig.gid group by u.uid,file_id;


create view if not exists local_rights as
select f.file_id, f.parent_id, f.name, uid, can_read,can_write,can_execute from s_file f left join user_rights r on f.file_id = r.file_id;

create view if not exists access_table as
with recursive
    access_t(file_id,path,uid,has_access) as (
       select file_id, "/" || name, uid, can_execute from local_rights where name = "galois"
       union all
       select lr.file_id,access_t.path || "/" || lr.name,lr.uid,lr.can_execute and access_t.has_access
          from local_rights lr join access_t on lr.parent_id = access_t.file_id and lr.uid = access_t.uid
       order by 1 desc
    )
    select access_t.* from access_t left join s_file on access_t.file_id = s_file.file_id where s_file.content is NULL;

create view if not exists global_rights as
select  lr.file_id,lr.uid, ifnull(at.path,"") || "/" || lr.name as path, 
   lr.can_write * ifnull(at.has_access,1) as can_write, 
   lr.can_read * ifnull(at.has_access,1) as can_read,
   lr.can_execute * ifnull(at.has_access,1) as can_execute
 from local_rights lr left join access_table at on lr.parent_id = at.file_id and lr.uid = at.uid;


