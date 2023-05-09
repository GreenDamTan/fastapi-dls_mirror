# Roadmap

I am planning to implement the following features in the future.


## HA - High Availability

Support Failover-Mode (secondary ip address) as in official DLS.

**Note**: There is no Load-Balancing / Round-Robin HA Mode supported! If you want to use that, consider to use 
Docker-Swarm with shared/cluster database (e.g. postgres).

*See [ha branch](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls/-/tree/ha) for current status.*


## UI - User Interface

Add a user interface to manage origins and leases.

*See [ui branch](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls/-/tree/ui) for current status.*


## Config Database

Instead of using environment variables, configuration files and manually create certificates, store configs and
certificates in database (like origins and leases). Also, there should be provided a startup assistant to prefill 
required attributes and create instance-certificates. This is more user-friendly and should improve fist setup.
