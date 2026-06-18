from pysnmp.hlapi import *

def get_sysname(ip, community="public"):
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161)),
            ContextData(),
            ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysName', 0))
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication:
            return {"error": str(errorIndication)}

        for varBind in varBinds:
            return {"device": str(varBind[1])}

    except Exception as e:
       return {"error": str(e)}
