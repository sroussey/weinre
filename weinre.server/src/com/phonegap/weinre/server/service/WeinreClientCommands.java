/*
 * PhoneGap is available under *either* the terms of the modified BSD license *or* the
 * MIT License (2008). See http://opensource.org/licenses/alphabetical for full text.
 * 
 * Copyright (c) 2010, IBM Corporation
 */

package com.phonegap.weinre.server.service;

import java.io.IOException;
import java.util.List;

import org.apache.wink.json4j.JSONArray;

import com.phonegap.weinre.server.Channel;
import com.phonegap.weinre.server.Client;
import com.phonegap.weinre.server.ConnectionManager;
import com.phonegap.weinre.server.Main;
import com.phonegap.weinre.server.Target;

/**
 * 
 */
public class WeinreClientCommands {

    /**
     * 
     */
    public void registerClient(Channel channel, String callbackId) throws IOException {
        Client client = new Client(channel);
        
        channel.sendCallback("WeinreClientEvents", callbackId, client.getName());
        channel.sendEvent("WeinreClientEvents", "serverProperties", Main.getSettings().asProperties());
    }

    /**
     * 
     */
    public void getTargets(Channel channel, String callbackId) throws IOException {
        List<Target> targets = ConnectionManager.$.getTargets();
        JSONArray targetResults = new JSONArray();
        
        for (Target target: targets) {
            targetResults.add(target.getDescription());
        }
        
        channel.sendCallback("WeinreClientEvents", callbackId, targetResults);
    }

    /**
     * 
     */
    public void getClients(Channel channel, String callbackId) throws IOException {
        List<Client> clients = ConnectionManager.$.getClients();
        JSONArray clientResults = new JSONArray();
        
        for (Client client: clients) {
            clientResults.add(client.getDescription());
        }
        
        channel.sendCallback("WeinreClientEvents", callbackId, clientResults);
    }

    /**
     * 
     */
    public void connectTarget(Channel channel, String clientId, String targetId, String callbackId) {
        Client client = ConnectionManager.$.getClient(clientId);
        if (client == null) return;

        Target target = ConnectionManager.$.getTarget(targetId);
        if (target == null) return;
        
        ConnectionManager.$.connect(client, target);
    }

    /**
     * 
     */
    public void disconnectTarget(Channel channel, String clientId, String callbackId) {
        Client client = ConnectionManager.$.getClient(clientId);
        if (client == null) return;
        
        Target target = client.getConnectedTarget();
        if (target == null) return;
        
        ConnectionManager.$.disconnect(client, target);
    }
    
}
