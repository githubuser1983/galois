# test,o=gauss,g=gauss:ro=1,wo=1,xo=1,rg=1;wg=0,xg=1,rot=1;wot=0,xot=1
curl -v -X PATCH -H "owner_name: root" \
                 -H "group_name: gauss" \
                 -H "read_owner: 1" \
                 -H "write_owner: 1" \
                 -H "execute_owner: 1" \
                 -H "read_group: 1" \
                 -H "write_group: 0" \
                 -H "execute_group: 1" \
                 -H "read_other: 0" \
                 -H "write_other: 0" \
                 -H "execute_other: 0" \
                 -H "username: gauss" -H "password: galois" http://127.0.0.1:8000/galois/home/gauss/test
