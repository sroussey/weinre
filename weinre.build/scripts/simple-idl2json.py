#!/usr/bin/env python

# ---
# PhoneGap is available under *either* the terms of the modified BSD license *or* the
# MIT License (2008). See http://opensource.org/licenses/alphabetical for full text.
# 
# Copyright (c) 2010, IBM Corporation
# ---

import os
import re
import sys
import json
import optparse

# see:
#    http://www.sitepen.com/blog/2009/06/23/unobtrusive-javascript-typing-via-json-schema-interfaces/
# for some info on JSON Schema for interfaces

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def main():
    
    # parse args
    parser = optparse.OptionParser()
    parser.add_option("--validate",  action="store_true",                 help="validate types")
    parser.add_option("--anyType",   action="append",     metavar="TYPE", help="treat TYPE as an any")
    (options, args) = parser.parse_args()
    
    if options.anyType:
        AnyTypes.extend(options.anyType)
    
    if len(args) <= 0: error("no input files specified")
    iFileName = args[0]
    
    if len(args) <= 1: 
        oFileName = "<stdout>"
    else:
        oFileName = args[1]
    
    # read input
    iFile = file(iFileName)
    content = iFile.read()
    iFile.close()
        
    # convert to JSONable
    module = parseIDL(content)
    
    if module["name"] == "core":
        if len(module["interfaces"]) == 1:
            if module["interfaces"][0]["name"] == "Inspector":
                splitInspectorInterfaces(module)

    # convert out parms to callback parms
    convertOutParms(module)
    
    # validate
    if options.validate: validate(module)

    # convert to JSON
    jsonModule = json.dumps(module, indent=3)
    
    # write output
    if oFileName == "<stdout>": 
        oFile = sys.stdout
    else:
        oFile = file(oFileName,"w")
        
    oFile.write(jsonModule)

    # close file
    if oFileName != "<stdout>": 
        oFile.close()
        log("generated json file '%s'" %oFileName)

#--------------------------------------------------------------------
# 
#--------------------------------------------------------------------
def convertOutParms(module):
    for interface in module["interfaces"]:
        
        if "methods" in interface:
            for method in interface["methods"]:
                method["callbackParameters"] = []
                newParameters = []
                
                for parameter in method["parameters"]:
                    if "out" in parameter:
                        method["callbackParameters"].append(parameter)
                    else:
                        newParameters.append(parameter)
                        
                method["parameters"] = newParameters

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def splitInspectorInterfaces(module):
    intfOrig             = module["interfaces"][0]
    intfWebInspector     = {}
    intfInspectorBackend = {}
    backendInterfaces    = {}
    
    intfWebInspector["name"]     = "WebInspector"
    intfWebInspector["methods"]  = []
    
    module["interfaces"] = [intfWebInspector]

    for method in intfOrig["methods"]:
        if "notify" not in method["extendedAttributes"]:
            if "handler" not in method["extendedAttributes"]:
                log("Inspector method %s has neither a 'notify' nor a 'handler' extended attribute" % (method["name"]))
                continue
            
            handlerInterfaceName = "WebInspector" + method["extendedAttributes"]["handler"] + "Handler"
            if handlerInterfaceName not in backendInterfaces:
                backendInterfaces[handlerInterfaceName] = {
                    "name": handlerInterfaceName,
                    "methods": []
                }
            
                module["interfaces"].append(backendInterfaces[handlerInterfaceName])
                
            handlerInterface = backendInterfaces[handlerInterfaceName]
                
            handlerInterface["methods"].append(method)
            continue
            
        for parameter in method["parameters"]:
            if "out" not in parameter:
                log("Inspector method %s has an unexpect non-out parameter %s" % (method["name"], parameter["name"]))
            else:
                del parameter["out"]
        
        intfWebInspector["methods"].append(method)

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def validate(module):
    interfaces = {}

    errors = False
    
    # build table of interface names
    for interface in module["interfaces"]:
        interfaces[interface["name"]] = interface
        
    # check interfaces
    for interface in module["interfaces"]:
        
        if "methods" in interface:
            for method in interface["methods"]:
                location = "%s.%s" % (interface["name"], method["name"])
                errors = checkType(location, interfaces, method["returns"]) or errors
                
                for parameter in method["parameters"]:
                    errors = checkType(location, interfaces, parameter["type"]) or errors
                
    
        if "attributes" in interface:
            for attribute in interface["attributes"]:
                location = "%s.%s" % (interface["name"], attribute["name"])
                errors = checkType(location, interfaces, attribute["type"]) or errors


#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def checkType(location, interfaces, type):
    typeName = type["name"]
    
    if typeName in BuiltInTypes: return False
    if typeName in interfaces: return False
    
    log("type '%s' is not valid in %s" % (typeName, location))
    
    return True
    

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def parseIDL(content):

    content = clean(content)

    match = PatternModule.match(content)
    if not match: error("no module found in input")
    
    moduleName = match.group(1).strip()
    content    = match.group(2)
    
    module = {}
    module["name"] = moduleName
    
    interfaces = []
    module["interfaces"] = interfaces
    
    while True:
        match = PatternInterface.match(content)
        if not match: break
        
        interfaceEAs  = match.group(1)
        interfaceName = match.group(2).strip()
        interfaceBody = match.group(3)
        content       = match.group(4)

        interface = {}
        interface["name"] = interfaceName
        parseExtendedAttributes(interface, interfaceEAs)
        
        interfaces.append(interface)
        
        while True:
            match = PatternMethod.match(interfaceBody)
            if match:
                method = parseMethod(match)
                if not "methods" in interface: interface["methods"] = []
                interface["methods"].append(method)
                
                interfaceBody = match.group(6)
                continue
                
            match = PatternAttribute.match(interfaceBody)
            if match:
                attribute = parseAttribute(match)
                if not "attributes" in interface: interface["attributes"] = []
                interface["attributes"].append(attribute)

                interfaceBody = match.group(5)
                continue

            if interfaceBody.strip() != "": 
                error("unexpected input: '%s'" % interfaceBody)
                
            break
        
    if content.strip() != "}": error("unexpected input: '%s'" % content)
    
    return module

#--------------------------------------------------------------------
# parse extended attributes
#--------------------------------------------------------------------
def parseExtendedAttributes(object, eaStrings):
    if not eaStrings: return
    if eaStrings == "": return
    
    eaStrings = eaStrings[1:-1]
    eaStrings = eaStrings.split(",")
    
    eas = {}
    for eaString in eaStrings:
        match = PatternExtendedAttribute.match(eaString)
        if not match:
            error("invalid extended attribute: '%s'" % eaString)
        
        if match.group(3):
            eas[match.group(1)] = match.group(3)
        else:
            eas[match.group(1)] = True
    
    if len(eas):
        object["extendedAttributes"] = eas

#--------------------------------------------------------------------
# parse method
#--------------------------------------------------------------------
def parseMethod(match):
    method = {}
    
    eas                  = match.group(1)
    method["returns"]    = getType(match.group(2), match.group(3))
    method["name"]       = match.group(4)
    method["parameters"] = parseMethodParameters(match.group(5))
    
    parseExtendedAttributes(method, eas)
    
    return method

#--------------------------------------------------------------------
# parse attribute
#--------------------------------------------------------------------
def parseAttribute(match):
    attribute = {}
    
    eas               = match.group(1)
    attribute["type"] = getType(match.group(2), match.group(3))
    attribute["name"] = match.group(4)

    parseExtendedAttributes(attribute, eas)

    return attribute

#--------------------------------------------------------------------
# get type information
#--------------------------------------------------------------------
def parseMethodParameters(parameterString):
    parameters = []
    
    parameterString = parameterString.strip()
    if "" == parameterString: return parameters
    
    parmStrings = parameterString.split(",")
    for parmString in parmStrings:
        parameter = {}
        
        parts = parmString.split()
        if parts[0] in ["in", "out"]:
            parmString = " ".join(parts[1:])
            if parts[0] == "out":
                parameter["out"] = True
                
        match = PatternParameter.match(parmString)
        if not match:
            error("error parsing parameter in '" + parameterString + "'")
            
        
        parameter["type"] = getType(match.group(1), match.group(2))
        
        if match.group(5):
            parameter["name"] = match.group(5)
        else:
            parameter["name"] = match.group(3)
        
        parameters.append(parameter)
        
    return parameters

#--------------------------------------------------------------------
# parse parameters
#--------------------------------------------------------------------
def getType(name, rank):
    name = name.strip()
    rank = PatternWhiteSpace.sub("", rank)
    
    origName = name
    
    if name == "long":      name = "int"
    if name == "int":       name = "int"
    if name == "double":    name = "float"
    if name == "unsigned":  name = "int"
    if name == "DOMString": name = "string"
    if name == "String":    name = "string"
    if name in AnyTypes:    name = "any"
    
    if name == "Array":
        return {
            "name": "any",
            "rank": 1
        }
    
    result = {}
    result["name"] = name
    
    if name != origName: result["originalName"] = origName
    
    if rank:
        if (rank == "[]"): 
            result["rank"] = 1
        else:
            error("currently only one dimensional arrays are supported: %s" % name)
        
    return result

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def clean(content):
    content = PatternCommentsPP.sub("", content)
    content = PatternPreprocessor.sub("", content)
    content = PatternNewLine.sub("", content)
    content = PatternComments.sub("", content)
    
    return content

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def log(message):
    message = "%s: %s" % (PROGRAM_NAME, message)
    print >>sys.stderr, message

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
def error(message):
    log(message)
    sys.exit(-1)

#--------------------------------------------------------------------
#
#--------------------------------------------------------------------
PROGRAM_NAME = os.path.basename(sys.argv[0])

PatternComments          = re.compile(r"/\*.*?\*/")
PatternCommentsPP        = re.compile(r"//.*$", re.MULTILINE)
PatternPreprocessor      = re.compile(r"^\s*#.*$", re.MULTILINE)
PatternNewLine           = re.compile(r"\n")
PatternWhiteSpace        = re.compile(r"\s")
PatternModule            = re.compile(r".*?\bmodule\b(.*?){(.*)")
PatternInterface         = re.compile(r".*?\binterface\b\s*(\[.*?\])?\s*(\w+)\s*{(.*?)}\s*;(.*)")
PatternMethod            = re.compile(r".*?(\[.*?\])?\s*(\w+)([\[\]\s]*)\s+(\w+)\s*\((.*?)\)\s*;?(.*)")
PatternAttribute         = re.compile(r".*?(\[.*?\])?\s*\battribute\s+(\w+)([\[\]\s]*)\s+(\w+)\s*;?(.*)")
PatternParameter         = re.compile(r".*?(\w+)([\[\]\s]*)\s+(\w+)(\s+(\w+))?")
PatternExtendedAttribute = re.compile(r"\s*(\w+)\s*(=\s*(\w+))?\s*")

BuiltInTypes = "void any boolean int float string".split()
AnyTypes     = "Object DOMObject".split()

main()
