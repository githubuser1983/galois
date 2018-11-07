# galois
Multi-User Rest-Api Server for Deploying Portable Format For analytics

How to use:
First install falcon and titus.
Then start for example with gunicorn server:api the server.
Go then at curls/ and execute some scripts to see what happens.

==Rest-API==
* each url for example /galois/home/gauss/ without a model is considered like a directory in linux
* each url for example /galois/home/gauss/iris.pfa with a model is considered like an executable file in linux
* each url belongs to one owner and one group.
* for each url there are the following rights: read, write, execute for owner,group,others; like in linux
* to make it more appealing, there will be command line tools which are named like the linux tools and work like those, for example:
  mkdir, ls, rm, adduser, chown, chmod etc -> this way, everyone who knows something about linux, should be able to use the api without high learning curve
  * Models:
    * POST : Execute a model
    * PUT : Create or update a model
    * GET : Read a model, download it
    * DELETE : Delete a model
    * w = write = PUT & DELETE
    * r = read = GET
    * x = execute = POST (with some json send to the file, so that it can read the json-file and execute the resource based on the contents of the json-file)
  * Directories:
    * r = read = GET, list files and (direct) subdirectories of this directory
    * w = write = POST & DELETE & PUT
    * e = execute = can access files in this directory whose name is known
    * POST = write a model to this directory, if it does not exist. Must specify the variable filename in HTTP-Header, whose value is the name of the model
    * DELETE = delete this directory if it is empty
    * PUT = create an empty subdirectoy in this directory if it does not exist, if the directory exists do not do anything --> PUT is idempotent; Must specify the variable filename in HTTP-Header, whose value is the name of the subdirectory to be created.
  * PATCH is for metadata

