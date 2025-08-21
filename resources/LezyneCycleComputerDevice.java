package com.lezyne.gpsally.services;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.location.Location;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import androidx.constraintlayout.core.motion.utils.TypedValues;
import androidx.lifecycle.CoroutineLiveDataKt;
import com.android.volley.RequestQueue;
import com.google.android.gms.maps.model.LatLng;
import com.google.common.net.HttpHeaders;
import com.google.firebase.analytics.FirebaseAnalytics;
import com.google.firebase.crashlytics.FirebaseCrashlytics;
import com.lezyne.gpsally.LezyneLinkApplication;
import com.lezyne.gpsally.Ride;
import com.lezyne.gpsally.Segment;
import com.lezyne.gpsally.api.ApiErrorCode;
import com.lezyne.gpsally.api.LezyneJsonApiRequest;
import com.lezyne.gpsally.api.models.LezyneApiModel;
import com.lezyne.gpsally.api.requests.liveTracking.EndLiveSession;
import com.lezyne.gpsally.api.requests.liveTracking.PostLiveSessionData;
import com.lezyne.gpsally.api.requests.liveTracking.StartLiveSession;
import com.lezyne.gpsally.broadcasts.BluetoothConnectionStateListener;
import com.lezyne.gpsally.broadcasts.MapFileUploadProgressReceiver;
import com.lezyne.gpsally.services.BluetoothLeService;
import com.lezyne.gpsally.tools.NavigationRouteCreator;
import com.lezyne.gpsally.tools.PackagedSegment;
import com.lezyne.gpsally.tools.RoutePathList;
import com.lezyne.gpsally.tools.RoutePathListManeuver;
import com.lezyne.gpsally.tools.RoutingProfile;
import com.lezyne.gpsally.tools.Settings;
import com.lezyne.gpsally.tools.SettingsParser;
import com.lezyne.gpsally.tools.StravaSegmentSyncStatus;
import com.lezyne.gpsally.tools.StringTool;
import com.lezyne.gpsally.ui.navigationTab.OfflineMap;
import dbg.Log;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.nio.BufferUnderflowException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.ConcurrentModificationException;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.UUID;
import kotlin.jvm.internal.ShortCompanionObject;
import org.apache.commons.lang3.CharEncoding;
import org.apache.commons.lang3.StringUtils;
import org.joda.time.DateTimeConstants;

/* loaded from: classes2.dex */
public class LezyneCycleComputerDevice extends BluetoothGattCallback {
    static final /* synthetic */ boolean $assertionsDisabled = false;
    public static final int GATT_SUCCESS = 0;
    public static final int GATT_SUCCESS_CONNECTION_LOST = 8;
    public static final int GATT_SUCCESS_DISCONNECT_REQUEST = 18;
    public static final int GATT_SUCCESS_DISCONNECT_REQUEST2 = 19;
    public static final int GATT_SUCCESS_ERROR_DISCONNECT = 133;
    public String address;
    public BluetoothDevice bluetoothDevice;
    protected BleFitFile currentDownload;
    public FileOutputStream currentDownloadOutputStream;
    public OfflineMap currentMapUpload;
    List<Segment> currentSegmentList;
    private int lastLiveSessionSampleSize;
    private long lastPostLiveSamplesTime;
    private BluetoothGattCharacteristic locationAndSpeedChar;
    private BluetoothGattService locationInfoService;
    public int mapFileBytesSent;
    public FileInputStream mapFileStream;
    protected long mapUploadStartTime;
    private NavigationRouteCreator routeCreator;
    public BluetoothLeService service;
    private ByteBuffer settingsInput;
    private int settingsInputSize;
    public static final UUID serviceUuid = UUID.fromString("904d0001-2ce9-078d-944d-263fd93d95b2");
    private static final UUID LOCATION_AND_SPEED = UUID.fromString("00002a67-0000-1000-8000-00805f9b34fb");
    private static final UUID LOCATION_AND_NAVIGATION = UUID.fromString("00001819-0000-1000-8000-00805f9b34fb");
    static int routeNum = 1;
    static int instanceCount = 0;
    public static final UUID CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    static int status257Count = 0;
    private static int badStatusCounter = 0;
    private boolean blockMessageQueue = false;
    private long blockMessageQueueTime = 0;
    private long rerouteRequestTime = 0;
    private ByteBuffer routeFile = null;
    long disconnectTime = 0;
    final UUID receiveDataCharacteristic = UUID.fromString("904d0002-2ce9-078d-944d-263fd93d95b2");
    final UUID transmitCharicteristic = UUID.fromString("904d0003-2ce9-078d-944d-263fd93d95b2");
    LiveSessionState liveSessionState = LiveSessionState.invalid;
    long downloadStartTime = 0;
    int downloadRetries = 0;
    private BleFitFile currentFileToDelete = null;
    BroadcastReceiver bsReciever = new BroadcastReceiver() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.3
        @Override // android.content.BroadcastReceiver
        public void onReceive(Context context, Intent intent) {
        }
    };
    private boolean isDownloading = false;
    private boolean isListingFiles = false;
    private Runnable fileListSendingTimeout = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.5
        @Override // java.lang.Runnable
        public void run() {
            LezyneCycleComputerDevice.this.isListingFiles = false;
        }
    };
    private Long mapsListRequestTime = 0L;
    private boolean liveSessionApiCallInProgress = false;
    boolean isLiveSessionStartPacketPending = false;
    private int liveTrackSessionNumber = 1;
    private HashMap<Integer, LiveSessionSample> liveSessionSamples = new HashMap<>();
    private RoutePathList currentDirections = null;
    int counter = 0;
    int rerouteInstance = 0;
    public RoutePathList lastRouteFile = null;
    public RoutePathList lastReroute = null;
    Runnable postRouteSendingComplete = null;
    int postNotificationRetries = 0;
    public boolean needToSubscribeToLocationUpdates = false;
    public boolean alreadySubscribedToLocationUpdates = false;
    private long tryingToConnectTime = 0;
    public GpsNavigationState gpsNavigationState = GpsNavigationState.Unknown;
    ArrayList<BleFitFile> currentFileList = new ArrayList<>();
    ConnectionState currentConnectionState = new ConnectionState();
    public final ArrayList<byte[]> outgoingMessageQue = new ArrayList<>();
    long connectGattInitiateTime = 0;
    public int suspiciousDisconnectsAboutResetIsNecessary = 0;
    public int suspiciousDisconnectsAboutBadEncryptionKey = 0;
    private Runnable connectTimeoutRunnable = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.19
        @Override // java.lang.Runnable
        public void run() {
            LezyneCycleComputerDevice.this.currentConnectionState.gattState = GattState.DISCONNECTED;
            Log.i("Rides", "connectTimeoutRunnable :: currentConnectionState.gattState =  GattState.DISCONNECTED; ");
        }
    };
    long calledDiscoverServicedTime = 0;
    private int discoverServicesAttempts = 0;
    public Runnable discoverServicesTimeoutRunnable = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.21
        @Override // java.lang.Runnable
        public void run() {
            Log.e("Rides", "Running: discoverServicesTimeoutRunnable ");
            LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.discoverServicesTimeoutRunnable);
            if (LezyneCycleComputerDevice.this.discoverServicesAttempts > 4) {
                LezyneCycleComputerDevice.this.currentConnectionState.gattState = GattState.DISCONNECTED;
            } else if (LezyneCycleComputerDevice.this.discoverServicesAttempts > 2) {
                if (LezyneCycleComputerDevice.this.service.bluetoothGatt != null) {
                    if (LezyneCycleComputerDevice.this.service.settings.getUseGattCloseNotDisconnect()) {
                        LezyneCycleComputerDevice.this.service.bluetoothGatt.close();
                    } else {
                        LezyneCycleComputerDevice.this.service.bluetoothGatt.disconnect();
                    }
                }
                LezyneCycleComputerDevice.this.service.Log("Multiple Discover Services Fails Disconnecting");
                LezyneCycleComputerDevice.this.service.whenWeDisconnect = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.21.1
                    @Override // java.lang.Runnable
                    public void run() {
                        LezyneCycleComputerDevice.this.service.Log("Multiple Discover Services Fails  Emergency reconnect");
                        LezyneCycleComputerDevice.this.service.connect(LezyneCycleComputerDevice.this.bluetoothDevice);
                    }
                };
            } else {
                LezyneCycleComputerDevice.this.discoverServicesAttempts++;
                LezyneCycleComputerDevice.this.service.bluetoothGatt.discoverServices();
                LezyneCycleComputerDevice.this.calledDiscoverServicedTime = SystemClock.elapsedRealtime();
                LezyneCycleComputerDevice.this.service.taskHandler.postDelayed(LezyneCycleComputerDevice.this.discoverServicesTimeoutRunnable, 10000L);
            }
            LezyneCycleComputerDevice.this.discoverServicesAttempts++;
        }
    };
    public Runnable discoverServicesDelayedTask = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.22
        @Override // java.lang.Runnable
        public void run() {
            LezyneCycleComputerDevice.this.suspiciousDisconnectsAboutResetIsNecessary = 0;
            LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.discoverServicesTimeoutRunnable);
            LezyneCycleComputerDevice.this.isSendingToBluetoothDevice = false;
            if (LezyneCycleComputerDevice.this.service.bluetoothGatt == null) {
                return;
            }
            try {
                LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.service.autoConnectPolling);
                LezyneCycleComputerDevice.this.service.taskHandler.postDelayed(LezyneCycleComputerDevice.this.service.autoConnectPolling, 10000L);
                if (!LezyneCycleComputerDevice.this.service.bluetoothGatt.discoverServices()) {
                    Log.e("Rides", "Discover services returned false");
                }
                LezyneCycleComputerDevice.this.discoverServicesAttempts = 0;
                LezyneCycleComputerDevice.this.calledDiscoverServicedTime = SystemClock.elapsedRealtime();
                LezyneCycleComputerDevice.this.service.taskHandler.postDelayed(LezyneCycleComputerDevice.this.discoverServicesTimeoutRunnable, 10000L);
                BluetoothConnectionStateListener.broadcastConnectingStatus(LezyneCycleComputerDevice.this.service, BluetoothConnectionStateListener.ConnectingStatus.DiscoveringServices, LezyneCycleComputerDevice.this.bluetoothDevice.getName(), 10000L);
            } catch (NullPointerException e) {
                e.printStackTrace();
            }
        }
    };
    public GpsDeviceInfo gpsDeviceInfo = new GpsDeviceInfo();
    long gattConnectionTime = 0;
    int statusPacketCounter = 0;
    protected boolean isSendingToBluetoothDevice = false;
    Runnable postMessageQueueRetryTask = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.24
        @Override // java.lang.Runnable
        public void run() {
            LezyneCycleComputerDevice.this.postMessageQue();
        }
    };
    private long postMessageQueBlockedUntil = 0;
    Runnable transferTimeoutAlarmRunnable = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.25
        @Override // java.lang.Runnable
        public void run() {
            Log.e("Rides", "transferTimeoutAlarmRunnable running");
            BleFitFile bleFitFileCurrentDownload = LezyneCycleComputerDevice.this.currentDownload();
            if (bleFitFileCurrentDownload != null && LezyneCycleComputerDevice.this.service.isConnected()) {
                bleFitFileCurrentDownload.hadErrorDownloading = true;
            }
            if (LezyneCycleComputerDevice.this.onTimeout()) {
                Log.i("Rides", "On Timeout @@");
                BluetoothFileInteractor.postDeviceErrorMessage(LezyneCycleComputerDevice.this.service);
                LezyneCycleComputerDevice.this.service.settings.clearPositiveUserEventCount();
            }
        }
    };
    String timeoutSender = "";
    Runnable fileUploadRequestTimeoutHandler = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.26
        @Override // java.lang.Runnable
        public void run() throws IOException {
            MapFileUploadProgressReceiver.postFileUploadFailed(LezyneCycleComputerDevice.this.service);
            LezyneCycleComputerDevice.this.service.startIdleTaskTimer();
            try {
                LezyneCycleComputerDevice.this.mapFileStream.close();
            } catch (Exception unused) {
            }
            LezyneCycleComputerDevice.this.mapFileStream = null;
            LezyneCycleComputerDevice.this.currentMapUpload = null;
            LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.sendPacketRunnable);
            LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.fileUploadRequestTimeoutHandler);
        }
    };
    Runnable sendPacketRunnable = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.27
        @Override // java.lang.Runnable
        public void run() {
            synchronized (LezyneCycleComputerDevice.this.service) {
                if (LezyneCycleComputerDevice.this.currentMapUpload != null) {
                    LezyneCycleComputerDevice.this.sendNextPacket();
                }
            }
        }
    };
    Runnable postMapSendingComplete = null;
    int currentMtu = 20;
    Runnable getMapListTimeout = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.29
        @Override // java.lang.Runnable
        public void run() {
            LezyneCycleComputerDevice.this.service.onMapFileListDownloaded(false);
        }
    };
    Runnable deleteMapTimeout = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.30
        @Override // java.lang.Runnable
        public void run() {
            LezyneCycleComputerDevice.this.service.onMapFileDeleted(LezyneCycleComputerDevice.this.mapFileToDelete, false);
            LezyneCycleComputerDevice.this.mapFileToDelete = null;
        }
    };
    OfflineMap mapFileToDelete = null;

    public enum BondState {
        NOT_BONDED,
        BONDED
    }

    public enum DataState {
        DISCONNECTED,
        WAITING,
        CONNECTED_SLOW_DATA,
        CONNECTED_HIGH_SPEED,
        SWITCHING_TO_HIGH_SPEED_MODE,
        SWITCHING_TO_LOW_SPEED_MODE
    }

    public enum GattState {
        DISCONNECTED,
        TRYING_TO_CONNECT,
        CONNECTED
    }

    public enum GpsNavigationState {
        Unavailable,
        Unknown,
        LifestyleWatch,
        Ready,
        InRoute
    }

    public static class LiveSessionSample {
        public Integer cadence;
        public int distance;
        public Integer heartRate;
        public float latitude;
        public float longitude;
        public Integer power;
        public int sessionId;
        public int speed;
        public float temperature;
        public int timestamp;
    }

    public enum LocationServiceState {
        DISCONNECTED,
        CONNECTED
    }

    enum WriteRxCharacteristicResult {
        success,
        failNoRecovery,
        failWithRecovery
    }

    public boolean canDoTurnByTurnNavigation() {
        return true;
    }

    public boolean canSyncSegments() {
        return true;
    }

    void logConnectionState() {
    }

    public boolean testBit(byte b, int i) {
        int i2 = 1 << i;
        return (b & i2) == i2;
    }

    private boolean internalRequestMtu(int i) {
        BluetoothGatt bluetoothGatt = this.service.bluetoothGatt;
        if (bluetoothGatt == null) {
            return false;
        }
        Log.i("MTU", "Requesting new MTU...");
        Log.i("MTU", "gatt.requestMtu(" + i + ")");
        return bluetoothGatt.requestMtu(i);
    }

    private void logError(String str) {
        Bundle bundle = new Bundle();
        GpsDeviceInfo gpsDeviceInfo = this.gpsDeviceInfo;
        if (gpsDeviceInfo != null) {
            bundle.putString("GPS", gpsDeviceInfo.deviceName());
        }
        bundle.putString("Phone", Build.MANUFACTURER + Build.MODEL);
        this.service.mFirebaseAnalytics.logEvent(str, bundle);
    }

    public void onDisconnectEvent() throws IOException {
        OfflineMap.INSTANCE.removeDeviceInformation(this.service);
        this.isSendingToBluetoothDevice = false;
        this.outgoingMessageQue.clear();
        this.service.taskHandler.removeCallbacks(this.discoverServicesTimeoutRunnable);
        long jElapsedRealtime = SystemClock.elapsedRealtime();
        long j = jElapsedRealtime - this.disconnectTime;
        if (this.currentConnectionState.gattState != GattState.DISCONNECTED || j >= 2000) {
            this.disconnectTime = jElapsedRealtime;
            if (this.currentConnectionState.dataState == DataState.CONNECTED_HIGH_SPEED) {
                this.service.downloadFilesQueue.clear();
            }
            this.currentConnectionState.dataState = DataState.DISCONNECTED;
            this.currentConnectionState.gattState = GattState.DISCONNECTED;
            Log.i("Rides", "currentConnectionState.gattState = GattState.DISCONNECTED;");
            this.currentConnectionState.locationServiceState = LocationServiceState.DISCONNECTED;
            this.service.onDisconnect();
            BleFitFile bleFitFileCurrentDownload = currentDownload();
            if (bleFitFileCurrentDownload != null && bleFitFileCurrentDownload.downloadRetries < 10) {
                bleFitFileCurrentDownload.downloadRetries++;
            }
            this.alreadySubscribedToLocationUpdates = false;
            if (this.currentMapUpload != null) {
                this.service.taskHandler.removeCallbacks(this.sendPacketRunnable);
                MapFileUploadProgressReceiver.postFileUploadFailed(this.service);
                this.currentMapUpload = null;
                try {
                    this.mapFileStream.close();
                } catch (Exception unused) {
                }
                this.mapFileStream = null;
            }
            this.service.taskHandler.removeCallbacks(this.service.autoConnectPolling);
            this.service.taskHandler.postDelayed(this.service.autoConnectPolling, 1000L);
        }
    }

    @Override // android.bluetooth.BluetoothGattCallback
    public void onDescriptorWrite(BluetoothGatt bluetoothGatt, BluetoothGattDescriptor bluetoothGattDescriptor, int i) {
        Log.i("Rides", "onDescriptorWrite status =" + i);
        this.service.taskHandler.removeCallbacks(this.discoverServicesTimeoutRunnable);
        if (this.service.bluetoothGatt != bluetoothGatt && !bluetoothGatt.getDevice().getAddress().equalsIgnoreCase(this.bluetoothDevice.getAddress())) {
            Log.e("Rides", "onDescriptorWrite callback from a different gatt device");
            return;
        }
        if (this.service.bluetoothGatt != bluetoothGatt) {
            this.service.bluetoothGatt = bluetoothGatt;
        }
        if (this.needToSubscribeToLocationUpdates) {
            try {
                Log.i("LiveTrack", " onDescriptorWrite + needToSubscribeToLocationUpdates");
                this.currentConnectionState.locationServiceState = LocationServiceState.CONNECTED;
                BluetoothGattService service = this.service.bluetoothGatt.getService(LOCATION_AND_NAVIGATION);
                this.locationInfoService = service;
                BluetoothGattCharacteristic characteristic = service.getCharacteristic(LOCATION_AND_SPEED);
                this.locationAndSpeedChar = characteristic;
                bluetoothGatt.setCharacteristicNotification(characteristic, true);
                BluetoothGattDescriptor descriptor = this.locationAndSpeedChar.getDescriptor(CCCD);
                descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                bluetoothGatt.writeDescriptor(descriptor);
                this.needToSubscribeToLocationUpdates = false;
            } catch (NullPointerException unused) {
                this.service.Log("Unable to write location characteristic descriptor");
                BluetoothConnectionStateListener.broadcastConnectingStatus(this.service, BluetoothConnectionStateListener.ConnectingStatus.ConnectedNoLocationService, this.bluetoothDevice.getName(), -1L);
            }
        }
    }

    public UUID receiveDataCharacteristic() {
        return this.receiveDataCharacteristic;
    }

    public UUID transmitDataCharacteristic() {
        return this.transmitCharicteristic;
    }

    public UUID lezyneDataService() {
        return serviceUuid;
    }

    void requestFileList() {
        Bundle bundle = new Bundle();
        bundle.putString(FirebaseAnalytics.Param.ITEM_ID, "List");
        bundle.putString(FirebaseAnalytics.Param.CONTENT_TYPE, "Fit files");
        this.service.mFirebaseAnalytics.logEvent(FirebaseAnalytics.Event.SELECT_CONTENT, bundle);
        this.currentFileList = new ArrayList<>();
        this.isListingFiles = true;
        byte[] bArrNewPacket = newPacket();
        bArrNewPacket[0] = OutgoingCommands.RequestFitFileList.byteValue();
        this.outgoingMessageQue.add(bArrNewPacket);
        postMessageQue();
        setTimeoutTimer("requestFileList", 15000);
    }

    boolean isWaiting() {
        return (this.isDownloading || this.isListingFiles || this.service.isSendingMapFile() || this.service.isSyncingSegments() || isSendingRouteFile()) ? false : true;
    }

    public void downloadFile(BleFitFile bleFitFile) {
        this.downloadStartTime = SystemClock.elapsedRealtime();
        this.isDownloading = true;
        byte[] bArrNewPacket = newPacket();
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArrNewPacket);
        bArrNewPacket[0] = OutgoingCommands.RequestFitFileDownload.byteValue();
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.putInt(1, bleFitFile.fileId);
        this.outgoingMessageQue.add(bArrNewPacket);
        this.currentDownload = bleFitFile;
        postMessageQue();
        setTimeoutTimer("downloadFile", 35000);
    }

    private void appendFileData(ByteBuffer byteBuffer) throws IOException {
        int i = this.currentDownload.fileSizeInBytes - this.currentDownload.downloadedBytes < 19 ? this.currentDownload.fileSizeInBytes - this.currentDownload.downloadedBytes : 19;
        try {
            this.currentDownloadOutputStream.write(byteBuffer.array(), 1, i);
            this.currentDownload.downloadedBytes += i;
            BluetoothFileDownloadProgressReceiver.INSTANCE.postProgress(this.service.getApplicationContext(), this.currentDownload.fileName, (int) ((this.currentDownload.downloadedBytes / this.currentDownload.fileSizeInBytes) * 100.0f), this.currentDownload.downloadedBytes, this.currentDownload.fileSizeInBytes);
        } catch (IOException unused) {
            this.service.settings.clearPositiveUserEventCount();
            BluetoothFileInteractor.postDeviceStorageFullError(this.service);
            this.service.onFileDownloadComplete(this.currentDownload, 0);
            this.isDownloading = false;
        } catch (ArrayIndexOutOfBoundsException | NullPointerException unused2) {
            this.service.onFileDownloadComplete(this.currentDownload, 0);
            this.isDownloading = false;
        }
    }

    public BleFitFile currentDownload() {
        return this.currentDownload;
    }

    public void deleteFile(BleFitFile bleFitFile) {
        this.currentFileToDelete = bleFitFile;
        byte[] bArrNewPacket = newPacket();
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArrNewPacket);
        bArrNewPacket[0] = OutgoingCommands.RequestFitFileDelete.byteValue();
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.putInt(1, bleFitFile.fileId);
        this.outgoingMessageQue.add(bArrNewPacket);
        postMessageQue();
        setTimeoutTimer("deleteFile", 10000);
    }

    public boolean isNavigating() {
        return this.gpsDeviceInfo.isNavigating || this.currentDirections != null;
    }

    public boolean isSendingRouteFile() {
        if (this.postRouteSendingComplete != null) {
            return true;
        }
        synchronized (this.outgoingMessageQue) {
            return this.outgoingMessageQue.size() > 0 && this.outgoingMessageQue.get(0)[0] == OutgoingCommands.NavFileUploadData.byteValue();
        }
    }

    private void handleStatusPacket(ByteBuffer byteBuffer) {
        Runnable runnable = this.postRouteSendingComplete;
        if (runnable != null) {
            this.postRouteSendingComplete = null;
            this.service.taskHandler.post(runnable);
        }
        Runnable runnable2 = this.postMapSendingComplete;
        if (runnable2 != null) {
            this.postMapSendingComplete = null;
            this.service.taskHandler.post(runnable2);
        }
        try {
            Byte bValueOf = Byte.valueOf(byteBuffer.get());
            int i = byteBuffer.get();
            String str = "";
            if (i > 60) {
                i -= 60;
                FirebaseCrashlytics.getInstance().setCustomKey("Japaneese", true);
            } else {
                FirebaseCrashlytics.getInstance().setCustomKey("Japaneese", false);
            }
            switch (i) {
                case 1:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y9Mini;
                    str = "Y9Mini";
                    break;
                case 2:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y9Power;
                    str = "Y9Power";
                    break;
                case 3:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y9Super;
                    str = "Y9Super";
                    break;
                case 4:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10Super;
                    str = "Y10Super";
                    break;
                case 5:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10Macro;
                    str = "Y10Macro";
                    break;
                case 6:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10Micro;
                    str = "Y10Micro";
                    break;
                case 7:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10MicroColor;
                    str = "Y10MicroColor";
                    break;
                case 8:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10MicroWatch;
                    str = "Y10MicroWatch";
                    break;
                case 9:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10WatchColor;
                    str = "Y10WatchColor";
                    break;
                case 10:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y10Mini;
                    str = "Y10Mini";
                    break;
                case 11:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y12Mega;
                    str = "Y12Mega";
                    break;
                case 12:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y12MegaColor;
                    str = "Y12MegaColor";
                    break;
                case 13:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y13Super;
                    str = "Y13Super";
                    break;
                case 14:
                    this.gpsDeviceInfo.model = GpsDeviceModel.Y13Macro;
                    str = "Y13Macro";
                    break;
                default:
                    this.gpsDeviceInfo.model = GpsDeviceModel.InvalidDevice;
                    break;
            }
            byteBuffer.get();
            this.gpsDeviceInfo.majorVer = byteBuffer.get();
            this.gpsDeviceInfo.minorVer = byteBuffer.get();
            FirebaseCrashlytics.getInstance().setCustomKey("GPS", str + StringUtils.SPACE + this.gpsDeviceInfo.majorVer + "." + this.gpsDeviceInfo.minorVer);
            switch (Byte.valueOf(byteBuffer.get()).byteValue()) {
                case 0:
                case 5:
                case 7:
                    this.gpsDeviceInfo.isNavigating = false;
                    break;
                case 1:
                case 2:
                case 3:
                case 4:
                case 6:
                case 8:
                    this.gpsDeviceInfo.isNavigating = true;
                    break;
            }
            if (this.gpsDeviceInfo.isNavigating && this.currentDirections != null) {
                this.currentDirections = null;
                this.rerouteInstance++;
            }
            this.gpsDeviceInfo.isRecording = false;
            switch (bValueOf.byteValue()) {
                case 2:
                    this.gpsDeviceInfo.isRecording = true;
                case 0:
                case 1:
                case 3:
                case 4:
                case 5:
                case 6:
                    this.gpsNavigationState = GpsNavigationState.Ready;
                    break;
                case 7:
                    this.gpsNavigationState = GpsNavigationState.LifestyleWatch;
                    if (isConnected() && this.currentDirections != null) {
                        this.currentDirections = null;
                        BluetoothNavigationProgressReceiver.postNavigationEnded(this.service);
                        break;
                    }
                    break;
                default:
                    this.gpsNavigationState = GpsNavigationState.Unknown;
                    break;
            }
            this.gpsDeviceInfo.gpsMode = byteBuffer.get();
            this.gpsDeviceInfo.bleSpeed = byteBuffer.get();
            this.service.settings.setNeedsFirmwareUpdate(this.gpsDeviceInfo);
            if (this.statusPacketCounter == 0) {
                SettingsParser.SettingCategory[] settingCategoryArr = {SettingsParser.SettingCategory.version};
                if ((this.gpsDeviceInfo.model == GpsDeviceModel.Y10Super || this.gpsDeviceInfo.model == GpsDeviceModel.Y10Macro || this.gpsDeviceInfo.model == GpsDeviceModel.Y10Micro || this.gpsDeviceInfo.model == GpsDeviceModel.Y10MicroColor || this.gpsDeviceInfo.model == GpsDeviceModel.Y10MicroWatch || this.gpsDeviceInfo.model == GpsDeviceModel.Y10WatchColor || this.gpsDeviceInfo.model == GpsDeviceModel.Y10Mini) && this.gpsDeviceInfo.minorVer == 39 && this.gpsDeviceInfo.majorVer == 31) {
                    final Runnable runnable3 = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.1
                        @Override // java.lang.Runnable
                        public void run() {
                            LezyneCycleComputerDevice.this.service.settings.setIsNewFirmwareAvailable(true);
                        }
                    };
                    this.service.taskHandler.postDelayed(runnable3, CoroutineLiveDataKt.DEFAULT_TIMEOUT);
                    this.service.requestSettings(settingCategoryArr, new BluetoothLeService.RequestSettingsListener() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.2
                        @Override // com.lezyne.gpsally.services.BluetoothLeService.RequestSettingsListener
                        public void completion(ByteBuffer byteBuffer2, int i2) {
                            if (byteBuffer2 == null) {
                                LezyneCycleComputerDevice.this.service.settings.setIsNewFirmwareAvailable(true);
                            } else if (byteBuffer2.array().length >= 8) {
                                LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(runnable3);
                                LezyneCycleComputerDevice.this.gpsDeviceInfo.freescaleMajorVersion = byteBuffer2.array()[3];
                                LezyneCycleComputerDevice.this.gpsDeviceInfo.freescaleMinorVersion = byteBuffer2.array()[7];
                                LezyneCycleComputerDevice.this.service.settings.setIsNewFirmwareAvailable(false);
                            } else {
                                LezyneCycleComputerDevice.this.gpsDeviceInfo.freescaleMajorVersion = 0;
                                LezyneCycleComputerDevice.this.gpsDeviceInfo.freescaleMinorVersion = 0;
                            }
                            Log.i("Setting", "Got Freescale version " + LezyneCycleComputerDevice.this.gpsDeviceInfo.freescaleMajorVersion + "." + LezyneCycleComputerDevice.this.gpsDeviceInfo.freescaleMinorVersion);
                        }
                    });
                }
            }
            this.statusPacketCounter++;
        } catch (BufferUnderflowException e) {
            e.printStackTrace();
            Log.e("BTLE", "Status packet too small!! " + byteBuffer.array().length);
        }
    }

    /* JADX WARN: Removed duplicated region for block: B:17:0x0045  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct code enable 'Show inconsistent code' option in preferences
    */
    void sendPhoneStatusPacket() {
        /*
            r8 = this;
            byte[] r0 = r8.newPacket()
            java.nio.ByteBuffer r1 = java.nio.ByteBuffer.wrap(r0)
            r2 = -1
            r3 = 1
            com.lezyne.gpsally.services.BluetoothLeService r4 = r8.service     // Catch: java.lang.IllegalArgumentException -> L32
            android.content.BroadcastReceiver r5 = r8.bsReciever     // Catch: java.lang.IllegalArgumentException -> L32
            android.content.IntentFilter r6 = new android.content.IntentFilter     // Catch: java.lang.IllegalArgumentException -> L32
            java.lang.String r7 = "android.intent.action.BATTERY_CHANGED"
            r6.<init>(r7)     // Catch: java.lang.IllegalArgumentException -> L32
            android.content.Intent r4 = r4.registerReceiver(r5, r6)     // Catch: java.lang.IllegalArgumentException -> L32
            java.lang.String r5 = "level"
            int r5 = r4.getIntExtra(r5, r2)     // Catch: java.lang.IllegalArgumentException -> L32
            java.lang.String r6 = "scale"
            int r4 = r4.getIntExtra(r6, r2)     // Catch: java.lang.IllegalArgumentException -> L2f
            com.lezyne.gpsally.services.BluetoothLeService r6 = r8.service     // Catch: java.lang.IllegalArgumentException -> L2d
            android.content.BroadcastReceiver r7 = r8.bsReciever     // Catch: java.lang.IllegalArgumentException -> L2d
            r6.unregisterReceiver(r7)     // Catch: java.lang.IllegalArgumentException -> L2d
            goto L38
        L2d:
            r6 = move-exception
            goto L35
        L2f:
            r6 = move-exception
            r4 = r3
            goto L35
        L32:
            r6 = move-exception
            r4 = r3
            r5 = r4
        L35:
            r6.printStackTrace()
        L38:
            if (r5 == r2) goto L45
            if (r4 == r2) goto L45
            float r2 = (float) r5
            float r4 = (float) r4
            float r2 = r2 / r4
            r4 = 1120403456(0x42c80000, float:100.0)
            float r2 = r2 * r4
            int r2 = (int) r2
            byte r2 = (byte) r2
            goto L47
        L45:
            r2 = 50
        L47:
            com.lezyne.gpsally.services.LezyneCycleComputerDevice$OutgoingCommands r4 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.OutgoingCommands.PhoneStatus
            byte r4 = r4.byteValue()
            r1.put(r4)
            r1.put(r2)
            java.util.TimeZone r2 = java.util.TimeZone.getDefault()
            java.util.Date r4 = new java.util.Date
            r4.<init>()
            long r4 = r4.getTime()
            int r2 = r2.getOffset(r4)
            r4 = 60000(0xea60, float:8.4078E-41)
            int r2 = r2 / r4
            float r2 = (float) r2
            r4 = 1114636288(0x42700000, float:60.0)
            float r2 = r2 / r4
            r4 = 1082130432(0x40800000, float:4.0)
            float r2 = r2 * r4
            int r2 = (int) r2
            byte r2 = (byte) r2
            r1.put(r2)
            com.lezyne.gpsally.tools.Settings r2 = new com.lezyne.gpsally.tools.Settings
            com.lezyne.gpsally.services.BluetoothLeService r4 = r8.service
            r2.<init>(r4)
            boolean r2 = r2.isLiveTrackingEnabled()
            r1.put(r2)
            r1.put(r3)
            java.util.ArrayList<byte[]> r1 = r8.outgoingMessageQue
            r1.add(r0)
            r8.postMessageQue()
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: com.lezyne.gpsally.services.LezyneCycleComputerDevice.sendPhoneStatusPacket():void");
    }

    public boolean isDownloading() {
        return this.isDownloading;
    }

    public void onServicesDiscovered(final BluetoothGatt bluetoothGatt) {
        List<BluetoothGattService> services;
        synchronized (this.service) {
            if (this.alreadySubscribedToLocationUpdates) {
                Log.e("Rides", "alreadySubscribedToLocationUpdates is true");
            }
            Log.i("Rides", "Stopping: discoverServicesTimeoutRunnable");
            this.service.taskHandler.removeCallbacks(this.discoverServicesTimeoutRunnable);
            this.bluetoothDevice = bluetoothGatt.getDevice();
            Log.i("Rides", " *&* onServicesDiscovered  called   .gattState = GattState.CONNECTED");
            try {
                services = bluetoothGatt.getServices();
            } catch (ConcurrentModificationException unused) {
                try {
                    Thread.sleep(250L);
                } catch (InterruptedException unused2) {
                }
                services = bluetoothGatt.getServices();
            }
        }
        if (services == null) {
            return;
        }
        final ArrayList arrayList = new ArrayList(services);
        this.service.taskHandler.post(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.4
            @Override // java.lang.Runnable
            public void run() {
                synchronized (LezyneCycleComputerDevice.this.service) {
                    BluetoothGatt bluetoothGatt2 = LezyneCycleComputerDevice.this.service.bluetoothGatt;
                    BluetoothGatt bluetoothGatt3 = bluetoothGatt;
                    if (bluetoothGatt2 != bluetoothGatt3 && !bluetoothGatt3.getDevice().getAddress().equalsIgnoreCase(LezyneCycleComputerDevice.this.bluetoothDevice.getAddress())) {
                        Log.e("Rides", "onServicesDiscovered on an old device " + bluetoothGatt.getDevice().getName() + "  !=  " + LezyneCycleComputerDevice.this.bluetoothDevice.getName());
                        return;
                    }
                    boolean z = false;
                    boolean z2 = false;
                    for (BluetoothGattService bluetoothGattService : arrayList) {
                        LezyneCycleComputerDevice.this.service.Log("Found Gatt Service:" + bluetoothGattService.getUuid().toString());
                        if (LezyneCycleComputerDevice.this.bluetoothDevice != null) {
                            LezyneCycleComputerDevice.this.bluetoothDevice.getBondState();
                        }
                        if (bluetoothGattService.getUuid().toString().equalsIgnoreCase(LezyneCycleComputerDevice.this.lezyneDataService().toString())) {
                            LezyneCycleComputerDevice.this.service.bluetoothGatt = bluetoothGatt;
                            LezyneCycleComputerDevice.this.enableReceiveDataNotification();
                            LezyneCycleComputerDevice.this.currentConnectionState.gattState = GattState.CONNECTED;
                            Log.i("Rides", " currentConnectionState.gattState = GattState.CONNECTED;");
                            if (LezyneCycleComputerDevice.this.currentConnectionState.dataState != DataState.SWITCHING_TO_HIGH_SPEED_MODE && LezyneCycleComputerDevice.this.currentConnectionState.dataState != DataState.SWITCHING_TO_LOW_SPEED_MODE) {
                                LezyneCycleComputerDevice.this.currentConnectionState.dataState = DataState.WAITING;
                            }
                            LezyneCycleComputerDevice.this.service.onConnect();
                            z = true;
                        }
                        if (bluetoothGattService.getUuid().toString().equalsIgnoreCase(LezyneCycleComputerDevice.LOCATION_AND_NAVIGATION.toString()) && !LezyneCycleComputerDevice.this.alreadySubscribedToLocationUpdates) {
                            Log.i("Rides", "Now we need to subscribe to location updates, but after the other one is complete.");
                            LezyneCycleComputerDevice.this.needToSubscribeToLocationUpdates = true;
                            LezyneCycleComputerDevice.this.alreadySubscribedToLocationUpdates = true;
                            z2 = true;
                        }
                    }
                    if (!z || !z2) {
                        LezyneCycleComputerDevice.this.service.settings.clearPositiveUserEventCount();
                        LezyneCycleComputerDevice.this.currentConnectionState.gattState = GattState.DISCONNECTED;
                        if (LezyneCycleComputerDevice.this.service.settings.getUseGattCloseNotDisconnect()) {
                            bluetoothGatt.close();
                        } else {
                            bluetoothGatt.disconnect();
                        }
                        LezyneCycleComputerDevice.this.service.autoReconnectState = BluetoothLeService.AutoReconnectState.Uninitialized;
                        LezyneCycleComputerDevice.this.service.autoReconnect();
                        if (!z) {
                            Log.e("Rides", "On services discovered but no data service");
                            LezyneCycleComputerDevice.this.service.Log("NO DATA Service  isNewGatt" + (bluetoothGatt == LezyneCycleComputerDevice.this.service.bluetoothGatt ? "same gatt" : "new gatt"));
                        }
                        if (!z2) {
                            Log.e("Rides", "On services discovered but no location service");
                            LezyneCycleComputerDevice.this.service.Log("NO Location Services   isNewGatt" + (bluetoothGatt == LezyneCycleComputerDevice.this.service.bluetoothGatt ? "same gatt" : "new gatt"));
                        }
                    } else {
                        LezyneCycleComputerDevice.this.service.Log("discovered all services   isNewGatt" + (bluetoothGatt == LezyneCycleComputerDevice.this.service.bluetoothGatt ? "same gatt" : "new gatt"));
                    }
                }
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void onDataAvailable(byte[] bArr) throws IOException {
        ByteBuffer byteBufferWrap;
        IncomingCommands incomingCommandsFromByte;
        byte[] bArrArray;
        int length;
        this.suspiciousDisconnectsAboutResetIsNecessary = 0;
        try {
            byteBufferWrap = ByteBuffer.wrap(bArr);
            byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
            incomingCommandsFromByte = IncomingCommands.fromByte(byteBufferWrap.get());
        } catch (BufferUnderflowException e) {
            Log.w("Rides", "Got lastConnectedAddress partial message");
            e.printStackTrace();
        }
        if (incomingCommandsFromByte == null) {
            return;
        }
        Log.i("BtleBytes", "<---" + incomingCommandsFromByte + "\t" + StringTool.toHex(bArr));
        Integer num = null;
        switch (AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[incomingCommandsFromByte.ordinal()]) {
            case 1:
                this.service.settings.clearPositiveUserEventCount();
                Bundle bundle = new Bundle();
                GpsDeviceInfo gpsDeviceInfo = this.gpsDeviceInfo;
                if (gpsDeviceInfo != null) {
                    bundle.putString("GPS", gpsDeviceInfo.deviceName());
                }
                bundle.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("TrainingSendError", bundle);
                return;
            case 2:
                this.service.settings.clearPositiveUserEventCount();
                Bundle bundle2 = new Bundle();
                GpsDeviceInfo gpsDeviceInfo2 = this.gpsDeviceInfo;
                if (gpsDeviceInfo2 != null) {
                    bundle2.putString("GPS", gpsDeviceInfo2.deviceName());
                }
                bundle2.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("MapFileSizeError", bundle2);
                return;
            case 3:
                this.service.taskHandler.removeCallbacks(this.getMapListTimeout);
                this.service.taskHandler.postDelayed(this.getMapListTimeout, CoroutineLiveDataKt.DEFAULT_TIMEOUT);
                handleMapFileData(byteBufferWrap);
                return;
            case 4:
                this.service.taskHandler.removeCallbacks(this.getMapListTimeout);
                this.service.onMapFileListDownloaded(true);
                return;
            case 5:
                this.service.settings.clearPositiveUserEventCount();
                this.service.onMapFileListDownloaded(false);
                this.service.taskHandler.removeCallbacks(this.getMapListTimeout);
                this.service.settings.clearPositiveUserEventCount();
                Bundle bundle3 = new Bundle();
                GpsDeviceInfo gpsDeviceInfo3 = this.gpsDeviceInfo;
                if (gpsDeviceInfo3 != null) {
                    bundle3.putString("GPS", gpsDeviceInfo3.deviceName());
                }
                bundle3.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("MapFileListError", bundle3);
                return;
            case 6:
                this.service.onMapFileDeleted(this.mapFileToDelete, true);
                this.mapFileToDelete = null;
                this.service.taskHandler.removeCallbacks(this.deleteMapTimeout);
                return;
            case 7:
                this.service.settings.clearPositiveUserEventCount();
                this.service.onMapFileDeleted(this.mapFileToDelete, false);
                this.mapFileToDelete = null;
                this.service.taskHandler.removeCallbacks(this.deleteMapTimeout);
                this.service.settings.clearPositiveUserEventCount();
                Bundle bundle4 = new Bundle();
                GpsDeviceInfo gpsDeviceInfo4 = this.gpsDeviceInfo;
                if (gpsDeviceInfo4 != null) {
                    bundle4.putString("GPS", gpsDeviceInfo4.deviceName());
                }
                bundle4.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("MapFileDeleteError", bundle4);
                return;
            case 8:
                if (this.service.settings.getDoNotSentMtuUpdate()) {
                    return;
                }
                this.blockMessageQueue = true;
                this.blockMessageQueueTime = SystemClock.elapsedRealtime();
                byte b = byteBufferWrap.get();
                Log.i("MTU", "GPS Requested " + ((int) b) + " mtu size");
                if (internalRequestMtu(b)) {
                    return;
                }
                Log.e("MTU", "MTU ERROR");
                return;
            case 9:
                try {
                    synchronized (this.service) {
                        try {
                            Log.i("Rides", "Got map file request");
                            ByteBuffer.wrap(newPacket());
                            bArrArray = newBigPacket().array();
                            length = bArrArray.length - 1;
                            if (this.currentMapUpload == null) {
                                Log.e("Rides", "Got map file request but did not have a current map");
                                int i = byteBufferWrap.getInt();
                                short s = byteBufferWrap.getShort();
                                Iterator<OfflineMap> it = OfflineMap.INSTANCE.getMapList(this.service).iterator();
                                while (true) {
                                    if (it.hasNext()) {
                                        OfflineMap next = it.next();
                                        if (next.getLzmFileSize() == i && next.getLzmFileCrc16() == s) {
                                            this.currentMapUpload = next;
                                        }
                                    }
                                }
                            }
                        } catch (IOException unused) {
                            MapFileUploadProgressReceiver.postFileUploadFailed(this.service);
                            this.service.startIdleTaskTimer();
                            try {
                                FileInputStream fileInputStream = this.mapFileStream;
                                if (fileInputStream != null) {
                                    fileInputStream.close();
                                }
                            } catch (IOException unused2) {
                            }
                            this.mapFileStream = null;
                            this.currentMapUpload = null;
                        }
                        if (this.currentMapUpload != null && this.mapFileStream != null) {
                            bArrArray[0] = OutgoingCommands.MapFileStart.byteValue();
                            this.mapFileStream.read(bArrArray, 1, length);
                            this.outgoingMessageQue.add(bArrArray);
                            this.mapFileBytesSent = length;
                            this.service.taskHandler.postDelayed(this.sendPacketRunnable, 20L);
                            this.mapUploadStartTime = SystemClock.elapsedRealtime();
                            return;
                        }
                        MapFileUploadProgressReceiver.postFileUploadFailed(this.service);
                        return;
                    }
                } finally {
                }
            case 10:
                this.service.settings.clearPositiveUserEventCount();
                synchronized (this.service) {
                    ArrayList arrayList = new ArrayList();
                    synchronized (this.outgoingMessageQue) {
                        Iterator<byte[]> it2 = this.outgoingMessageQue.iterator();
                        while (it2.hasNext()) {
                            byte[] next2 = it2.next();
                            switch (next2[0]) {
                                case 45:
                                case 46:
                                case 47:
                                case 48:
                                case 49:
                                case 50:
                                case 51:
                                case 52:
                                    arrayList.add(next2);
                                    break;
                            }
                        }
                        this.outgoingMessageQue.removeAll(arrayList);
                    }
                    this.service.taskHandler.removeCallbacks(this.sendPacketRunnable);
                    MapFileUploadProgressReceiver.postFileUploadFailed(this.service);
                    this.service.startIdleTaskTimer();
                    try {
                        FileInputStream fileInputStream2 = this.mapFileStream;
                        if (fileInputStream2 != null) {
                            fileInputStream2.close();
                        }
                    } catch (IOException unused3) {
                    }
                    this.service.settings.clearPositiveUserEventCount();
                    this.mapFileStream = null;
                    this.currentMapUpload = null;
                    Bundle bundle5 = new Bundle();
                    GpsDeviceInfo gpsDeviceInfo5 = this.gpsDeviceInfo;
                    if (gpsDeviceInfo5 != null) {
                        bundle5.putString("GPS", gpsDeviceInfo5.deviceName());
                    }
                    bundle5.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                    this.service.mFirebaseAnalytics.logEvent("MapFileError", bundle5);
                }
                return;
            case 11:
            default:
                return;
            case 12:
                setTimeoutTimer("FitFileTransferStart", 15000);
                try {
                    BleFitFile bleFitFile = new BleFitFile();
                    this.currentDownload = bleFitFile;
                    bleFitFile.fileId = byteBufferWrap.getInt();
                    this.currentDownload.fileSizeInBytes = byteBufferWrap.getInt();
                    BleFitFile bleFitFile2 = this.currentDownload;
                    bleFitFile2.fileName = String.format("%08X.fit", Integer.valueOf(bleFitFile2.fileId));
                    if (!this.isDownloading) {
                        this.service.fileUploadManager.addFileToUploadQueue(this.currentDownload, this.service);
                        BleFitFile bleFitFile3 = this.currentDownload;
                        bleFitFile3.rideTitle = bleFitFile3.prettyName(this.service);
                        FitFileUploadManager.postFileTitleSaved(this.service, this.currentDownload);
                    }
                    this.isDownloading = true;
                    this.currentDownload.downloadedBytes = 0;
                    File file = Ride.file(this.service.getApplicationContext(), this.currentDownload.fileName);
                    Log.i("Rides", "Saving file " + file.getAbsolutePath());
                    file.getParentFile().getParentFile().mkdirs();
                    file.getParentFile().mkdirs();
                    Iterator<BleFitFile> it3 = currentDeviceFiles().iterator();
                    boolean z = false;
                    while (it3.hasNext()) {
                        if (it3.next().fileName.equalsIgnoreCase(this.currentDownload.fileName)) {
                            z = true;
                        }
                    }
                    if (!z) {
                        currentDeviceFiles().add(this.currentDownload);
                        BluetoothLeService bluetoothLeService = this.service;
                        BleFitFile bleFitFile4 = this.currentDownload;
                        Ride.fromBleFitFile(bluetoothLeService, bleFitFile4, bleFitFile4.prettyName(bluetoothLeService), "").save(this.service);
                        if (new Settings(this.service).isLoggedIn()) {
                            this.service.fileUploadManager.addFileToUploadQueue(this.currentDownload, this.service);
                            FitFileUploadManager.postFileTitleSaved(this.service, this.currentDownload);
                        }
                    }
                    this.currentDownloadOutputStream = new FileOutputStream(file);
                    this.service.stopIdleTaskTimer();
                    return;
                } catch (IOException unused4) {
                    this.isDownloading = false;
                    this.service.settings.clearPositiveUserEventCount();
                    Bundle bundle6 = new Bundle();
                    GpsDeviceInfo gpsDeviceInfo6 = this.gpsDeviceInfo;
                    if (gpsDeviceInfo6 != null) {
                        bundle6.putString("GPS", gpsDeviceInfo6.deviceName());
                    }
                    bundle6.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                    this.service.mFirebaseAnalytics.logEvent("FitFileIOError", bundle6);
                    return;
                }
            case 13:
                setTimeoutTimer("FitFileTransferData", 15000);
                if (this.isDownloading) {
                    appendFileData(byteBufferWrap);
                } else {
                    Log.e("Rides", "got FitFileTransferData but no FitFileTransferStart");
                }
                this.service.stopIdleTaskTimer();
                return;
            case 14:
                Log.i("Rides", "Got FitFileTransferEnd");
                cancelTimeoutTimer("FitFileTransferEnd");
                if (this.isDownloading) {
                    appendFileData(byteBufferWrap);
                    this.isDownloading = false;
                    BluetoothLeService bluetoothLeService2 = this.service;
                    BleFitFile bleFitFile5 = this.currentDownload;
                    bluetoothLeService2.onFileDownloadComplete(bleFitFile5, bleFitFile5.downloadedBytes);
                    this.currentDownload = null;
                    return;
                }
                Log.e("Rides", "got FitFileTransferEnd but no FitFileTransferStart");
                return;
            case 15:
                this.currentConnectionState.dataState = DataState.SWITCHING_TO_HIGH_SPEED_MODE;
                return;
            case 16:
                if (this.currentConnectionState.dataState == DataState.DISCONNECTED && this.service.currentDevice == this) {
                    this.service.onConnect();
                }
                this.service.stopIdleTaskTimer();
                this.currentConnectionState.dataState = DataState.CONNECTED_HIGH_SPEED;
                return;
            case 17:
                this.currentConnectionState.dataState = DataState.SWITCHING_TO_LOW_SPEED_MODE;
                long jElapsedRealtime = SystemClock.elapsedRealtime() - this.downloadStartTime;
                if (currentDownload() == null || jElapsedRealtime >= 2000 || this.isDownloading) {
                    return;
                }
                Log.e("Rides", "got SwitchingToLowSpeed while downlod pending");
                this.service.taskHandler.postDelayed(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.6
                    @Override // java.lang.Runnable
                    public void run() {
                        LezyneCycleComputerDevice lezyneCycleComputerDevice = LezyneCycleComputerDevice.this;
                        lezyneCycleComputerDevice.downloadFile(lezyneCycleComputerDevice.currentDownload);
                    }
                }, 2000L);
                return;
            case 18:
                Log.i("Rides", "ConnectedInLowSpeed");
                if (this.currentConnectionState.dataState == DataState.DISCONNECTED && this.service.currentDevice == this) {
                    this.service.onConnect();
                }
                this.currentConnectionState.dataState = DataState.CONNECTED_SLOW_DATA;
                long jElapsedRealtime2 = SystemClock.elapsedRealtime() - this.downloadStartTime;
                if (currentDownload() != null && jElapsedRealtime2 < 8000 && !this.isDownloading) {
                    Log.e("Rides", "got SwitchingToLowSpeed while downlod pending");
                    this.service.taskHandler.postDelayed(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.7
                        @Override // java.lang.Runnable
                        public void run() {
                            LezyneCycleComputerDevice lezyneCycleComputerDevice = LezyneCycleComputerDevice.this;
                            lezyneCycleComputerDevice.downloadFile(lezyneCycleComputerDevice.currentDownload);
                        }
                    }, 1000L);
                }
                this.service.startIdleTaskTimer();
                return;
            case 19:
                appendToDebugLog(bArr);
                return;
            case 20:
                Bundle bundle7 = new Bundle();
                GpsDeviceInfo gpsDeviceInfo7 = this.gpsDeviceInfo;
                if (gpsDeviceInfo7 != null) {
                    bundle7.putString("GPS", gpsDeviceInfo7.deviceName());
                }
                bundle7.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("ErrorPacket", bundle7);
                this.service.settings.clearPositiveUserEventCount();
                return;
            case 21:
                cancelTimeoutTimer("FileDeleteConfirmation");
                BleFitFile bleFitFile6 = this.currentFileToDelete;
                this.currentFileToDelete = null;
                this.service.onFileDeleteComplete(bleFitFile6);
                return;
            case 22:
                this.service.taskHandler.removeCallbacks(this.fileListSendingTimeout);
                this.service.taskHandler.postDelayed(this.fileListSendingTimeout, CoroutineLiveDataKt.DEFAULT_TIMEOUT);
                if (!this.isListingFiles) {
                    this.currentFileList = new ArrayList<>();
                    this.isListingFiles = true;
                }
                handleNewFileName(byteBufferWrap);
                this.service.stopIdleTaskTimer();
                return;
            case 23:
                Log.i("Rides", "Got GPSReadyToReceiveSegmentList");
                sendCurrentSegmentList();
                this.service.stopIdleTaskTimer();
                return;
            case 24:
                Log.i("Rides", "Got SegmentFileRequest");
                setTimeoutTimer("SegmentFileRequest", DateTimeConstants.MILLIS_PER_MINUTE);
                sendSegmentDataFile(byteBufferWrap.getLong());
                this.service.stopIdleTaskTimer();
                return;
            case 25:
                cancelTimeoutTimer("SegmentFileRequestEnd");
                this.service.onSegmentSyncDone();
                StravaSegmentSyncStatus stravaSegmentSyncStatus = new StravaSegmentSyncStatus();
                stravaSegmentSyncStatus.state = StravaSegmentSyncStatus.SegmentSyncState.syncSuccees;
                stravaSegmentSyncStatus.date = System.currentTimeMillis();
                try {
                    stravaSegmentSyncStatus.numberOfSyncedSegments = this.currentSegmentList.size();
                } catch (NullPointerException unused5) {
                    stravaSegmentSyncStatus.numberOfSyncedSegments = 0;
                }
                StravaSegmentSyncStatus.saveSyncState(this.service, stravaSegmentSyncStatus);
                this.service.stopIdleTaskTimer();
                return;
            case 26:
                handleStatusPacket(byteBufferWrap);
                sendPhoneStatusPacket();
                BluetoothNavigationProgressReceiver.setTransmittingRouteFile(false);
                return;
            case 27:
                this.currentDirections = null;
                BluetoothNavigationProgressReceiver.postNavigationEnded(this.service);
                return;
            case 28:
                this.currentDirections = null;
                BluetoothNavigationProgressReceiver.postNavigationTransmitFail(this.service);
                this.service.settings.clearPositiveUserEventCount();
                Bundle bundle8 = new Bundle();
                GpsDeviceInfo gpsDeviceInfo8 = this.gpsDeviceInfo;
                if (gpsDeviceInfo8 != null) {
                    bundle8.putString("GPS", gpsDeviceInfo8.deviceName());
                }
                bundle8.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("RoutePinTimeout", bundle8);
                return;
            case 29:
                this.rerouteRequestTime = System.currentTimeMillis();
                int i2 = byteBufferWrap.getInt();
                int i3 = byteBufferWrap.getInt();
                char c = (char) byteBufferWrap.get();
                if (!isDownloading()) {
                    sendNavigationReroute(i3, i2, c);
                }
                this.service.stopIdleTaskTimer();
                return;
            case 30:
                int i4 = byteBufferWrap.getInt();
                Integer numValueOf = Integer.valueOf(byteBufferWrap.get());
                Integer numValueOf2 = Integer.valueOf(byteBufferWrap.get());
                Integer numValueOf3 = Integer.valueOf(byteBufferWrap.getShort() & ShortCompanionObject.MAX_VALUE);
                float f = byteBufferWrap.getFloat();
                Integer numValueOf4 = (numValueOf.intValue() == -1 || numValueOf.intValue() == 0) ? null : Integer.valueOf(numValueOf.intValue() & 255);
                Integer numValueOf5 = numValueOf2.intValue() == -1 ? null : Integer.valueOf(numValueOf2.intValue() & 255);
                if (numValueOf3.intValue() != 32767) {
                    num = numValueOf3;
                }
                onLiveSensorData(i4, numValueOf4, numValueOf5, num, f);
                this.service.stopIdleTaskTimer();
                return;
            case 31:
                Log.i("LiveTrack", "Got session status");
                LiveSessionState liveSessionStateFromByte = LiveSessionState.fromByte(byteBufferWrap.get());
                if (this.liveSessionState != liveSessionStateFromByte) {
                    onLiveSessionStateChanged(liveSessionStateFromByte);
                    return;
                }
                return;
            case 32:
                sendCurrentRouteFile();
                return;
            case 33:
                this.settingsInput = ByteBuffer.wrap(new byte[1000]);
                this.settingsInputSize = byteBufferWrap.getInt();
                return;
            case 34:
                appendSettingsInput(byteBufferWrap);
                return;
            case 35:
                this.service.onSettingsSendError();
                this.service.settings.clearPositiveUserEventCount();
                Bundle bundle9 = new Bundle();
                GpsDeviceInfo gpsDeviceInfo9 = this.gpsDeviceInfo;
                if (gpsDeviceInfo9 != null) {
                    bundle9.putString("GPS", gpsDeviceInfo9.deviceName());
                }
                bundle9.putString("Phone", Build.MANUFACTURER + Build.MODEL);
                this.service.mFirebaseAnalytics.logEvent("SettingsSendError", bundle9);
                return;
        }
        Log.w("Rides", "Got lastConnectedAddress partial message");
        e.printStackTrace();
    }

    private void postLiveSessionSamplesToServer() {
        HashMap<Integer, LiveSessionSample> map = this.liveSessionSamples;
        if (map == null) {
            return;
        }
        synchronized (map) {
            if (this.liveSessionApiCallInProgress) {
                return;
            }
            this.liveSessionApiCallInProgress = true;
            this.lastPostLiveSamplesTime = SystemClock.elapsedRealtime();
            final HashMap map2 = new HashMap();
            map2.putAll(this.liveSessionSamples);
            RequestQueue requestQueue = ((LezyneLinkApplication) this.service.getApplicationContext()).requestQue;
            final ArrayList arrayList = new ArrayList();
            Iterator<Integer> it = this.liveSessionSamples.keySet().iterator();
            while (it.hasNext()) {
                LiveSessionSample liveSessionSample = this.liveSessionSamples.get(it.next());
                if (liveSessionSample.timestamp != 0 && liveSessionSample.latitude != 0.0f && liveSessionSample.longitude != 0.0f && liveSessionSample.temperature != 0.0f && liveSessionSample.sessionId == this.liveTrackSessionNumber) {
                    arrayList.add(liveSessionSample);
                }
            }
            this.liveSessionSamples.clear();
            this.lastLiveSessionSampleSize = 0;
            Collections.sort(arrayList, new Comparator<LiveSessionSample>() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.8
                @Override // java.util.Comparator
                public int compare(LiveSessionSample liveSessionSample2, LiveSessionSample liveSessionSample3) {
                    return liveSessionSample2.timestamp - liveSessionSample3.timestamp;
                }
            });
            Log.i("LiveTrack", "Have samples to post " + arrayList.size());
            if (arrayList.size() == 0) {
                this.liveSessionApiCallInProgress = false;
            } else {
                requestQueue.add(PostLiveSessionData.postLiveSessionData(this.service, arrayList, new LezyneJsonApiRequest.LezyneResponseListener(this.service, new LezyneJsonApiRequest.ApiCompletionListener() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.9
                    @Override // com.lezyne.gpsally.api.LezyneJsonApiRequest.ApiCompletionListener
                    public void success(LezyneApiModel lezyneApiModel) {
                        Log.i("LiveTrack", "Successfully posted live session data");
                        LezyneCycleComputerDevice.this.service.Log("Posted " + arrayList.size() + " samples");
                        synchronized (map2) {
                            LezyneCycleComputerDevice.this.liveSessionApiCallInProgress = false;
                        }
                    }

                    @Override // com.lezyne.gpsally.api.LezyneJsonApiRequest.ApiCompletionListener
                    public void fail(ApiErrorCode apiErrorCode) {
                        LezyneCycleComputerDevice.this.service.Log("Failed to post " + arrayList.size() + " samples");
                        synchronized (LezyneCycleComputerDevice.this.liveSessionSamples) {
                            if (map2 == LezyneCycleComputerDevice.this.liveSessionSamples) {
                                Log.e("LiveTrack", "ERROR posting live session data");
                                Iterator it2 = arrayList.iterator();
                                while (it2.hasNext()) {
                                    LiveSessionSample liveSessionSample2 = (LiveSessionSample) it2.next();
                                    if (liveSessionSample2.sessionId == LezyneCycleComputerDevice.this.liveTrackSessionNumber) {
                                        LezyneCycleComputerDevice.this.liveSessionSamples.put(Integer.valueOf(liveSessionSample2.timestamp), liveSessionSample2);
                                    }
                                }
                            }
                            LezyneCycleComputerDevice.this.liveSessionApiCallInProgress = false;
                        }
                    }
                })));
            }
        }
    }

    private void postLiveSessionStart(final Runnable runnable) {
        synchronized (this) {
            if (this.isLiveSessionStartPacketPending) {
                return;
            }
            this.isLiveSessionStartPacketPending = true;
            ((LezyneLinkApplication) this.service.getApplicationContext()).requestQue.add(StartLiveSession.startLiveSession(this.service, new LezyneJsonApiRequest.LezyneResponseListener(this.service, new LezyneJsonApiRequest.ApiCompletionListener() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.10
                @Override // com.lezyne.gpsally.api.LezyneJsonApiRequest.ApiCompletionListener
                public void success(LezyneApiModel lezyneApiModel) {
                    Log.i("LiveTrack", "Succesfully starting live session");
                    LezyneCycleComputerDevice.this.service.Log("Post live sessoion start - SUCCESS");
                    synchronized (this) {
                        runnable.run();
                        LezyneCycleComputerDevice.this.isLiveSessionStartPacketPending = false;
                    }
                }

                @Override // com.lezyne.gpsally.api.LezyneJsonApiRequest.ApiCompletionListener
                public void fail(ApiErrorCode apiErrorCode) {
                    Log.i("LiveTrack", "ERROR starting live session");
                    LezyneCycleComputerDevice.this.service.Log("Post live sessoion start - FAIL");
                    synchronized (this) {
                        LezyneCycleComputerDevice.this.isLiveSessionStartPacketPending = false;
                    }
                }
            })));
        }
    }

    private void postLiveSessionEnd() {
        this.service.Log("Post live sessoion end");
        synchronized (this.liveSessionSamples) {
            Log.i("LiveTrack", "postLiveSessionEnd");
            HashMap<Integer, LiveSessionSample> map = this.liveSessionSamples;
            if (map != null && map.size() > 0) {
                postLiveSessionSamplesToServer();
                this.liveSessionSamples.clear();
            }
            ((LezyneLinkApplication) this.service.getApplicationContext()).requestQue.add(EndLiveSession.endLiveSession(this.service, new LezyneJsonApiRequest.LezyneResponseListener(this.service, new LezyneJsonApiRequest.ApiCompletionListener() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.11
                @Override // com.lezyne.gpsally.api.LezyneJsonApiRequest.ApiCompletionListener
                public void success(LezyneApiModel lezyneApiModel) {
                    Log.i("LiveTrack", "Succesfully ended live session");
                }

                @Override // com.lezyne.gpsally.api.LezyneJsonApiRequest.ApiCompletionListener
                public void fail(ApiErrorCode apiErrorCode) {
                    Log.i("LiveTrack", "ERROR ending live session");
                }
            })));
        }
    }

    private void onLiveSensorData(int i, Integer num, Integer num2, Integer num3, float f) {
        HashMap<Integer, LiveSessionSample> map;
        BluetoothLeService.liveTrackDataPacketCount++;
        synchronized (this.liveSessionSamples) {
            if (this.service.settings.isLiveTrackingEnabled()) {
                int i2 = AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[this.liveSessionState.ordinal()];
                if (i2 == 1 || i2 == 2) {
                    synchronized (this.liveSessionSamples) {
                        if (!this.gpsDeviceInfo.isRecording) {
                            return;
                        }
                        this.liveTrackSessionNumber++;
                        Log.i("LiveTrack", "Create new hash map");
                        this.liveSessionSamples.clear();
                        this.lastLiveSessionSampleSize = 0;
                        BluetoothLeService.liveTrackSessionStartCount++;
                        BluetoothLeService.liveTrackSessionStartTime = System.currentTimeMillis();
                        postLiveSessionStart(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.12
                            @Override // java.lang.Runnable
                            public void run() {
                                LezyneCycleComputerDevice.this.liveSessionState = LiveSessionState.start;
                            }
                        });
                    }
                } else {
                    if (i2 == 3 || i2 == 4) {
                    }
                    long jElapsedRealtime = SystemClock.elapsedRealtime() - this.lastPostLiveSamplesTime;
                    map = this.liveSessionSamples;
                    if (map != null && map.size() - this.lastLiveSessionSampleSize > 30 && jElapsedRealtime > 30000) {
                        this.lastLiveSessionSampleSize = this.liveSessionSamples.size();
                        postLiveSessionSamplesToServer();
                        BluetoothLeService.liveTrackSessionDataCount++;
                        BluetoothLeService.liveTrackSessionDataTime = System.currentTimeMillis();
                    }
                    Log.i("LiveTrack", "liveTrackSessionNumber=" + this.liveTrackSessionNumber + "  sampleCount=" + this.liveSessionSamples.size() + "     timeDiff = " + jElapsedRealtime);
                }
                synchronized (this.liveSessionSamples) {
                    Integer numValueOf = Integer.valueOf(i);
                    LiveSessionSample liveSessionSample = this.liveSessionSamples.get(numValueOf);
                    if (liveSessionSample == null) {
                        liveSessionSample = new LiveSessionSample();
                    }
                    liveSessionSample.cadence = num2;
                    liveSessionSample.power = num3;
                    liveSessionSample.timestamp = i;
                    liveSessionSample.heartRate = num;
                    liveSessionSample.temperature = f;
                    liveSessionSample.sessionId = this.liveTrackSessionNumber;
                    Log.i("LiveTrack", "Adding sample at " + numValueOf);
                    this.liveSessionSamples.put(numValueOf, liveSessionSample);
                }
                long jElapsedRealtime2 = SystemClock.elapsedRealtime() - this.lastPostLiveSamplesTime;
                map = this.liveSessionSamples;
                if (map != null) {
                    this.lastLiveSessionSampleSize = this.liveSessionSamples.size();
                    postLiveSessionSamplesToServer();
                    BluetoothLeService.liveTrackSessionDataCount++;
                    BluetoothLeService.liveTrackSessionDataTime = System.currentTimeMillis();
                }
                Log.i("LiveTrack", "liveTrackSessionNumber=" + this.liveTrackSessionNumber + "  sampleCount=" + this.liveSessionSamples.size() + "     timeDiff = " + jElapsedRealtime2);
            } else {
                Log.i("LiveTrack", "Live track disabled");
            }
        }
    }

    private void onLiveSessionStateChanged(final LiveSessionState liveSessionState) {
        int i;
        Log.i("LiveTrack", "Live session state changed");
        int i2 = AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[liveSessionState.ordinal()];
        if (i2 == 1 || i2 == 2) {
            this.gpsDeviceInfo.isRecording = false;
        } else if (i2 == 4) {
            this.gpsDeviceInfo.isRecording = true;
        }
        synchronized (this.liveSessionSamples) {
            if (this.service.settings.isLiveTrackingEnabled()) {
                if (liveSessionState == LiveSessionState.start && ((i = AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[this.liveSessionState.ordinal()]) == 1 || i == 2)) {
                    BluetoothLeService.liveTrackSessionStartCount++;
                    BluetoothLeService.liveTrackSessionStartTime = System.currentTimeMillis();
                    postLiveSessionStart(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.13
                        @Override // java.lang.Runnable
                        public void run() {
                            LezyneCycleComputerDevice.this.liveTrackSessionNumber++;
                            LezyneCycleComputerDevice.this.liveSessionSamples = new HashMap();
                            LezyneCycleComputerDevice.this.lastLiveSessionSampleSize = 0;
                            LezyneCycleComputerDevice.this.liveSessionState = liveSessionState;
                        }
                    });
                }
                if (liveSessionState == LiveSessionState.end) {
                    int i3 = AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[this.liveSessionState.ordinal()];
                    if (i3 == 1 || i3 == 3 || i3 == 4 || i3 == 5) {
                        BluetoothLeService.liveTrackSessionEndCount++;
                        BluetoothLeService.liveTrackSessionEndTime = System.currentTimeMillis();
                        postLiveSessionEnd();
                        this.liveTrackSessionNumber++;
                    }
                    this.liveSessionState = liveSessionState;
                }
            }
        }
    }

    private void appendToDebugLog(byte[] bArr) {
        char[] cArr = new char[20];
        int i = 0;
        while (i < 19) {
            int i2 = i + 1;
            if (bArr[i2] == 0) {
                return;
            }
            cArr[i] = (char) bArr[i];
            i = i2;
        }
    }

    private void handleNewFileName(ByteBuffer byteBuffer) {
        byte b = byteBuffer.get();
        int[] iArr = {byteBuffer.getInt(), byteBuffer.getInt(), byteBuffer.getInt(), byteBuffer.getInt()};
        for (int i = 0; i < b; i++) {
            if (iArr[i] != 0) {
                BleFitFile bleFitFile = new BleFitFile();
                bleFitFile.fileName = String.format("%08X.fit", Integer.valueOf(iArr[i]));
                bleFitFile.fileId = iArr[i];
                this.currentFileList.add(bleFitFile);
            }
        }
        if (b < 4) {
            this.isListingFiles = false;
            this.service.onFileListingDone();
            this.service.taskHandler.removeCallbacks(this.fileListSendingTimeout);
            cancelTimeoutTimer("FileListSending");
            return;
        }
        setTimeoutTimer("FileListSending", 5000);
    }

    public void sendSegmentDataFile(long j) {
        PackagedSegment packagedSegmentFromFile = PackagedSegment.fromFile(this.service, j);
        byte[] bArr = packagedSegmentFromFile.buffer;
        short s = packagedSegmentFromFile.size;
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(newPacket());
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.put(OutgoingCommands.SegmentFileUploadStart.byteValue());
        byteBufferWrap.putLong(j);
        byteBufferWrap.putInt(s);
        this.outgoingMessageQue.add(byteBufferWrap.array());
        int i = 0;
        while (true) {
            int i2 = s - i;
            if (i2 > 19) {
                ByteBuffer byteBufferWrap2 = ByteBuffer.wrap(newPacket());
                byteBufferWrap2.order(ByteOrder.LITTLE_ENDIAN);
                byteBufferWrap2.put(OutgoingCommands.SegmentFileUploadData.byteValue());
                byteBufferWrap2.put(bArr, i, 19);
                this.outgoingMessageQue.add(byteBufferWrap2.array());
                i += 19;
            } else {
                ByteBuffer byteBufferWrap3 = ByteBuffer.wrap(newPacket());
                byteBufferWrap3.order(ByteOrder.LITTLE_ENDIAN);
                byteBufferWrap3.put(OutgoingCommands.SegmentFileUploadEnd.byteValue());
                byteBufferWrap3.put(bArr, i, i2);
                this.outgoingMessageQue.add(byteBufferWrap3.array());
                postMessageQue();
                return;
            }
        }
    }

    public void cancelSegmentSync() {
        byte[] bArr = new byte[20];
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.put(OutgoingCommands.SegmentUpdateCancel.byteValue());
        this.outgoingMessageQue.add(bArr);
        cancelTimeoutTimer("cancelSegmentSync");
    }

    public void sendSegments(List<Segment> list) throws IOException {
        Log.i("Rides", "  CALLED : sendSegments");
        this.currentSegmentList = list;
        byte[] bArr = new byte[20];
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.put(OutgoingCommands.NewSegmentListReady.byteValue());
        byteBufferWrap.put((byte) list.size());
        this.outgoingMessageQue.add(bArr);
        postMessageQue();
        setTimeoutTimer("sendSegments", DateTimeConstants.MILLIS_PER_MINUTE);
        StravaSegmentSyncStatus stravaSegmentSyncStatus = new StravaSegmentSyncStatus();
        stravaSegmentSyncStatus.state = StravaSegmentSyncStatus.SegmentSyncState.syncBtle;
        stravaSegmentSyncStatus.date = System.currentTimeMillis();
        StravaSegmentSyncStatus.saveSyncState(this.service, stravaSegmentSyncStatus);
    }

    void sendCurrentSegmentList() {
        setTimeoutTimer("sendCurrentSegmentList", DateTimeConstants.MILLIS_PER_MINUTE);
        for (int i = 0; i < this.currentSegmentList.size(); i++) {
            Segment segment = this.currentSegmentList.get(i);
            byte[] bArr = new byte[20];
            ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
            byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
            if (i == this.currentSegmentList.size() - 1) {
                byteBufferWrap.put(OutgoingCommands.SegmentListItemDone.byteValue());
            } else {
                byteBufferWrap.put(OutgoingCommands.SegmentListItem.byteValue());
            }
            byteBufferWrap.putLong(segment.getId());
            int i2 = (int) (segment.getStartLocation().latitude * 1.1930464E7d);
            int i3 = (int) (segment.getStartLocation().longitude * 1.1930464E7d);
            byteBufferWrap.putInt(i2);
            byteBufferWrap.putInt(i3);
            byteBufferWrap.putChar((char) segment.getSegmentCrcValue(this.service));
            byteBufferWrap.put((byte) segment.getGoalCompare(this.service));
            this.outgoingMessageQue.add(bArr);
        }
        postMessageQue();
    }

    public void cancelNavigationDirections() {
        this.rerouteInstance++;
        byte[] bArr = new byte[20];
        ByteBuffer.wrap(bArr).put(OutgoingCommands.NavigationPhoneCancel_V2.byteValue());
        this.outgoingMessageQue.add(bArr);
        this.currentDirections = null;
        postMessageQue();
        this.gpsDeviceInfo.isNavigating = false;
    }

    private void sendNavigationReroute(int i, int i2, char c) {
        int i3 = this.rerouteInstance + 1;
        this.rerouteInstance = i3;
        sendNavigationReroute(i, i2, c, i3);
    }

    private void sendNavigationReroute(int i, int i2, final char c, final int i3) {
        BluetoothNavigationProgressReceiver.postRerouteStarted(this.service);
        Location lastKnownLocation = LezyneLocationManager.INSTANCE.getInstance(this.service).getLastKnownLocation();
        LatLng latLng = new LatLng(lastKnownLocation.getLatitude(), lastKnownLocation.getLongitude());
        double d = i / 1.1930464E7d;
        double d2 = i2 / 1.1930464E7d;
        LatLng latLng2 = new LatLng(d, d2);
        Log.i("TRIM", "sendNavigationReroute to " + d + "," + d2 + "  with provider:" + c);
        NavigationRouteCreator.RouteRequest routeRequest = new NavigationRouteCreator.RouteRequest();
        routeRequest.start = latLng;
        routeRequest.end = latLng2;
        this.routeCreator.getReroute(this.gpsDeviceInfo, routeRequest, c, new NavigationRouteCreator.RouteResultListener() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.14
            /* JADX WARN: Can't fix incorrect switch cases order, some code will duplicate */
            /* JADX WARN: Removed duplicated region for block: B:23:0x0066  */
            @Override // com.lezyne.gpsally.tools.NavigationRouteCreator.RouteResultListener
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct code enable 'Show inconsistent code' option in preferences
            */
            public void onNewRoute(com.lezyne.gpsally.tools.RoutePathList r7) {
                /*
                    r6 = this;
                    r0 = 1
                    java.lang.Boolean r1 = java.lang.Boolean.valueOf(r0)
                    r7.isReroute = r0
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r2 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    boolean r2 = r2.isDownloading()
                    if (r2 != 0) goto Lbb
                    r2 = 0
                    java.lang.Boolean r2 = java.lang.Boolean.valueOf(r2)
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    if (r3 == 0) goto L66
                    int[] r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r4 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r4 = r4.gpsDeviceInfo
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceModel r4 = r4.model
                    int r4 = r4.ordinal()
                    r3 = r3[r4]
                    switch(r3) {
                        case 5: goto L49;
                        case 6: goto L49;
                        case 7: goto L49;
                        case 8: goto L49;
                        case 9: goto L49;
                        case 10: goto L49;
                        case 11: goto L49;
                        case 12: goto L2c;
                        case 13: goto L2c;
                        case 14: goto L2c;
                        case 15: goto L2c;
                        default: goto L2b;
                    }
                L2b:
                    goto L66
                L2c:
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    int r3 = r3.majorVer
                    r4 = 32
                    if (r3 != r4) goto L40
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    int r3 = r3.minorVer
                    r5 = 14
                    if (r3 >= r5) goto L67
                L40:
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    int r3 = r3.majorVer
                    if (r3 <= r4) goto L66
                    goto L67
                L49:
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    int r3 = r3.majorVer
                    r4 = 31
                    if (r3 != r4) goto L5d
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    int r3 = r3.minorVer
                    r5 = 38
                    if (r3 >= r5) goto L67
                L5d:
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r3 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceInfo r3 = r3.gpsDeviceInfo
                    int r3 = r3.majorVer
                    if (r3 <= r4) goto L66
                    goto L67
                L66:
                    r1 = r2
                L67:
                    boolean r1 = r1.booleanValue()
                    java.lang.String r2 = "TRIM"
                    if (r1 == 0) goto L82
                    java.lang.String r1 = "Using route trimming"
                    dbg.Log.i(r2, r1)
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.tools.NavigationRouteCreator r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.m378$$Nest$fgetrouteCreator(r1)
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r2 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.tools.RoutePathList r2 = r2.lastRouteFile
                    r1.trimRoute(r7, r2)
                    goto L87
                L82:
                    java.lang.String r1 = "NOT trimming route"
                    dbg.Log.i(r2, r1)
                L87:
                    int r1 = r2
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r2 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    int r2 = r2.rerouteInstance
                    java.lang.String r3 = "Rides"
                    if (r1 == r2) goto L97
                    java.lang.String r7 = "Ignoring reroute due to reroute instance"
                    dbg.Log.i(r3, r7)
                    return
                L97:
                    char r1 = r3
                    r2 = 90
                    if (r1 == r2) goto Laf
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.tools.RoutePathList r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.m374$$Nest$fgetcurrentDirections(r1)
                    if (r1 == 0) goto Lb6
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    com.lezyne.gpsally.tools.RoutePathList r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.m374$$Nest$fgetcurrentDirections(r1)
                    boolean r1 = r1.linkRoute
                    if (r1 == 0) goto Lb6
                Laf:
                    r7.linkRoute = r0
                    java.lang.String r1 = "Reroute back to the saved route"
                    dbg.Log.i(r3, r1)
                Lb6:
                    com.lezyne.gpsally.services.LezyneCycleComputerDevice r1 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.this
                    r1.sendNavigationDirections(r7, r0)
                Lbb:
                    return
                */
                throw new UnsupportedOperationException("Method not decompiled: com.lezyne.gpsally.services.LezyneCycleComputerDevice.AnonymousClass14.onNewRoute(com.lezyne.gpsally.tools.RoutePathList):void");
            }

            @Override // com.lezyne.gpsally.tools.NavigationRouteCreator.RouteResultListener
            public void onError() {
                Log.i("Rides", "Ignoring reroute fail due to reroute instance");
            }
        });
    }

    private float distanceFloat(LatLng latLng, LatLng latLng2) {
        double d = latLng.latitude - latLng2.latitude;
        double d2 = latLng.longitude - latLng2.longitude;
        return (float) Math.sqrt((d * d) + (d2 * d2));
    }

    /* JADX WARN: Multi-variable type inference failed */
    private ByteBuffer buildRouteFile(RoutePathList routePathList) {
        if (routePathList.maneuvers == null || routePathList.maneuvers.size() == 0) {
            RoutePathListManeuver routePathListManeuver = new RoutePathListManeuver();
            routePathListManeuver.maneuver = RoutePathListManeuver.Maneuver.FullMap;
            LatLng latLng = routePathList.decodePolyline().get(0);
            routePathListManeuver.latitude = (int) (latLng.latitude * 1.1930464E7d);
            routePathListManeuver.longitude = (int) (latLng.longitude * 1.1930464E7d);
            routePathListManeuver.setStreetName("");
            routePathList.maneuvers.add(routePathListManeuver);
            RoutePathListManeuver routePathListManeuver2 = new RoutePathListManeuver();
            routePathListManeuver2.maneuver = RoutePathListManeuver.Maneuver.FullMap;
            routePathListManeuver2.latitude = (int) (latLng.latitude * 1.1930464E7d);
            routePathListManeuver2.longitude = (int) (latLng.longitude * 1.1930464E7d);
            routePathListManeuver2.setStreetName("");
            routePathList.maneuvers.add(routePathListManeuver2);
            RoutePathListManeuver routePathListManeuver3 = new RoutePathListManeuver();
            routePathListManeuver3.maneuver = RoutePathListManeuver.Maneuver.FullMap;
            routePathListManeuver3.latitude = (int) (routePathList.destinationLatitude * 1.1930464E7d);
            routePathListManeuver3.longitude = (int) (routePathList.destinationLongitude * 1.1930464E7d);
            routePathListManeuver3.setStreetName("");
            routePathList.maneuvers.add(routePathListManeuver3);
        }
        byte[] polylineBytes = routePathList.getPolylineBytes();
        if (routePathList.maneuvers != null) {
            routePathList.determinePolylineOffsetsForManeuvers();
        }
        ByteBuffer byteBufferAllocate = ByteBuffer.allocate(200000);
        byteBufferAllocate.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferAllocate.putInt(routePathList.destinationLongitude);
        byteBufferAllocate.putInt(routePathList.destinationLatitude);
        byteBufferAllocate.put((byte) routePathList.routingProfile.gpsDeviceProviderId());
        boolean z = routePathList.isSavedRoute;
        int i = z;
        if (routePathList.isTrimmedReroute) {
            i = (z ? 1 : 0) | 4;
        }
        byteBufferAllocate.put((byte) i);
        byteBufferAllocate.putShort((short) polylineBytes.length);
        Log.i("Nav", "Polyline bytes = " + polylineBytes.length);
        byteBufferAllocate.putShort((short) routePathList.maneuvers.size());
        if (!routePathList.linkRoute) {
            byteBufferAllocate.put((byte) 0);
            this.lastRouteFile = routePathList;
            this.lastReroute = null;
        } else {
            this.lastReroute = routePathList;
            byteBufferAllocate.put((byte) 1);
            if (routePathList.isTrimmedReroute) {
                byte[] bytes = "route".getBytes(Charset.forName(CharEncoding.UTF_8));
                for (int i2 = 0; i2 < 7; i2++) {
                    if (i2 < bytes.length) {
                        byteBufferAllocate.put(bytes[i2]);
                    } else {
                        byteBufferAllocate.put((byte) 0);
                    }
                }
                byteBufferAllocate.putInt(routePathList.distanceAfterTrim);
                byteBufferAllocate.putShort((short) routePathList.linkedRoutePolylineCount);
            } else {
                byte[] bytes2 = "route".getBytes(Charset.forName(CharEncoding.UTF_8));
                for (int i3 = 0; i3 < 13; i3++) {
                    if (i3 < bytes2.length) {
                        byteBufferAllocate.put(bytes2[i3]);
                    } else {
                        byteBufferAllocate.put((byte) 0);
                    }
                }
            }
            Log.i("Rides", "Making route link to saved route");
        }
        Log.i("Nav", "polyline size " + polylineBytes.length);
        byteBufferAllocate.put(polylineBytes);
        for (int i4 = 0; i4 < routePathList.decodePolyline().size(); i4++) {
            routePathList.decodePolyline().get(i4);
        }
        if (routePathList.maneuvers != null) {
            Iterator<RoutePathListManeuver> it = routePathList.maneuvers.iterator();
            int i5 = 0;
            while (it.hasNext()) {
                RoutePathListManeuver next = it.next();
                i5++;
                byteBufferAllocate.putInt(next.longitude);
                byteBufferAllocate.putInt(next.latitude);
                byteBufferAllocate.putShort((short) next.polylineCount);
                byteBufferAllocate.put(next.maneuver.getValue());
                Log.i("RidesNav", "   Maneuver[" + i5 + "] " + next.polylineCount + "  " + next.maneuver + "  " + next.getStreetName());
                try {
                    byte[] bytes3 = next.getStreetName().getBytes(Charset.forName(CharEncoding.UTF_8));
                    byte length = (byte) bytes3.length;
                    byteBufferAllocate.put(length);
                    for (byte b = 0; b < length; b = (byte) (b + 1)) {
                        byteBufferAllocate.put(bytes3[b]);
                    }
                } catch (NullPointerException unused) {
                    byteBufferAllocate.put((byte) 0);
                }
            }
        } else {
            byteBufferAllocate.put((byte) 0);
        }
        char cGetCRC16 = 0;
        for (int i6 = 0; i6 < byteBufferAllocate.position(); i6++) {
            cGetCRC16 = PackagedSegment.GetCRC16(cGetCRC16, byteBufferAllocate.get(i6));
        }
        byteBufferAllocate.putShort((short) byteBufferAllocate.position());
        byteBufferAllocate.putShort((short) cGetCRC16);
        return byteBufferAllocate;
    }

    private void sendCurrentRouteFile() {
        byte[] bArrNewPacket;
        ByteBuffer byteBufferWrap;
        int length;
        ByteBuffer byteBuffer = this.routeFile;
        if (byteBuffer == null) {
            Log.e("Rides", "Can't send route file, null buffer");
            return;
        }
        int iPosition = byteBuffer.position();
        Boolean boolValueOf = Boolean.valueOf(Build.VERSION.SDK_INT == 26);
        if (this.gpsDeviceInfo.majorVer < 31) {
            boolValueOf = false;
        }
        if (this.gpsDeviceInfo.majorVer == 31 && this.gpsDeviceInfo.minorVer < 60) {
            boolValueOf = false;
        }
        int i = 0;
        int i2 = 0;
        while (iPosition > 0) {
            i++;
            if (Build.VERSION.SDK_INT == 26 && boolValueOf.booleanValue()) {
                byteBufferWrap = newBigPacket();
                bArrNewPacket = byteBufferWrap.array();
                length = bArrNewPacket.length - 1;
            } else {
                bArrNewPacket = newPacket();
                byteBufferWrap = ByteBuffer.wrap(bArrNewPacket);
                length = 19;
            }
            if (iPosition == this.routeFile.position()) {
                byteBufferWrap.put(OutgoingCommands.NavFileUploadDataStart.byteValue());
            } else if (iPosition >= length) {
                byteBufferWrap.put(OutgoingCommands.NavFileUploadData.byteValue());
            } else {
                Log.i("BTLT", "Pushing nav upload end packet " + i);
                byteBufferWrap.put(OutgoingCommands.NavFileUploadEnd.byteValue());
                length = iPosition;
            }
            for (int i3 = 0; i3 < length; i3++) {
                byteBufferWrap.put(this.routeFile.get(i2));
                i2++;
                iPosition--;
            }
            this.outgoingMessageQue.add(bArrNewPacket);
        }
        Log.i("Rides", "Set route file to null 1");
        this.routeFile = null;
        postMessageQue();
        this.service.settings.incrementPositiveEventCount();
        this.postRouteSendingComplete = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.15
            @Override // java.lang.Runnable
            public void run() {
                if (LezyneCycleComputerDevice.this.postRouteSendingComplete != null) {
                    LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.postRouteSendingComplete);
                }
                LezyneCycleComputerDevice.this.postRouteSendingComplete = null;
                BluetoothNavigationProgressReceiver.postRouteSendingComplete(LezyneCycleComputerDevice.this.service);
            }
        };
    }

    public void sendNavigationDirections(final RoutePathList routePathList, final boolean z) {
        if (routePathList == null) {
            return;
        }
        if (z && routePathList.linkRoute && this.outgoingMessageQue.size() > 0) {
            this.service.taskHandler.postDelayed(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.16
                @Override // java.lang.Runnable
                public void run() {
                    LezyneCycleComputerDevice.this.sendNavigationDirections(routePathList, z);
                }
            }, 1000L);
            return;
        }
        if (this.currentDirections == routePathList) {
            return;
        }
        Bundle bundle = new Bundle();
        if (routePathList.isSavedRoute) {
            bundle.putString(FirebaseAnalytics.Param.ITEM_ID, "Saved Route");
        } else if (routePathList.isReroute) {
            bundle.putString(FirebaseAnalytics.Param.ITEM_ID, "Reroute");
        } else if (routePathList.isKomoot) {
            bundle.putString(FirebaseAnalytics.Param.ITEM_ID, "Komoot");
        } else {
            bundle.putString(FirebaseAnalytics.Param.ITEM_ID, "Point To Point");
        }
        bundle.putString(FirebaseAnalytics.Param.CONTENT_TYPE, "Route");
        this.service.mFirebaseAnalytics.logEvent(FirebaseAnalytics.Event.SELECT_CONTENT, bundle);
        if (!routePathList.isKomoot && !routePathList.isSavedRoute) {
            Bundle bundle2 = new Bundle();
            switch (AnonymousClass31.$SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[routePathList.routingProfile.provider.ordinal()]) {
                case 1:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Provider-A");
                    break;
                case 2:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Provider-B");
                    break;
                case 3:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Provider-C");
                    break;
                case 4:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Provider-D");
                    break;
                case 5:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Mountain Bike");
                    break;
                case 6:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Road Bike");
                    break;
                case 7:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Easy Ride");
                    break;
                case 8:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Shortest");
                    break;
                case 9:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Hiking");
                    break;
                case 10:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, "Commuter");
                    break;
                case 11:
                    bundle2.putString(FirebaseAnalytics.Param.ITEM_ID, TypedValues.Custom.NAME);
                    break;
            }
            bundle2.putString(FirebaseAnalytics.Param.CONTENT_TYPE, "Provider");
            this.service.mFirebaseAnalytics.logEvent(FirebaseAnalytics.Event.SELECT_CONTENT, bundle2);
        }
        if (routePathList.decodePolyline() == null) {
            routePathList.getPolylineBytes();
        }
        ByteBuffer byteBufferBuildRouteFile = buildRouteFile(routePathList);
        this.currentDirections = routePathList;
        byte b = 1;
        BluetoothNavigationProgressReceiver.setTransmittingRouteFile(true);
        byte[] bArr = new byte[20];
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.put(OutgoingCommands.NavigationNewFile.byteValue());
        byteBufferWrap.putInt(byteBufferBuildRouteFile.position());
        String str = "route";
        if (!routePathList.isSavedRoute) {
            str = "route" + routeNum;
            int i = routeNum + 1;
            routeNum = i;
            if (i == 3) {
                routeNum = 1;
            }
        }
        byteBufferWrap.put(str.getBytes());
        this.outgoingMessageQue.add(bArr);
        byte[] bArr2 = new byte[20];
        ByteBuffer byteBufferWrap2 = ByteBuffer.wrap(bArr2);
        byteBufferWrap2.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap2.put(OutgoingCommands.NavigationNewFileDest.byteValue());
        byteBufferWrap2.putInt(this.currentDirections.destinationLongitude);
        byteBufferWrap2.putInt(this.currentDirections.destinationLatitude);
        byteBufferWrap2.put((byte) this.currentDirections.routingProfile.gpsDeviceProviderId());
        if (this.currentDirections.isSavedRoute) {
            byteBufferWrap2.put((byte) 1);
        } else {
            byteBufferWrap2.put((byte) 0);
        }
        if (z) {
            byteBufferWrap2.put((byte) 0);
        } else {
            byteBufferWrap2.put((byte) 1);
        }
        if (!this.currentDirections.isSavedRoute) {
            b = this.currentDirections.isTrimmedReroute ? (byte) 3 : (byte) 2;
        }
        byteBufferWrap2.put(b);
        this.outgoingMessageQue.add(bArr2);
        postMessageQue();
        this.routeFile = byteBufferBuildRouteFile;
        Log.i("Rides", "Set route file to lastConnectedAddress new file");
    }

    public boolean onTimeout() throws IOException {
        if (this.isDownloading) {
            this.service.onFileDownloadComplete(this.currentDownload, 0);
        }
        if (this.service.isSyncingSegments) {
            this.service.onSegmentSyncFailed();
            StravaSegmentSyncStatus stravaSegmentSyncStatus = new StravaSegmentSyncStatus();
            stravaSegmentSyncStatus.state = StravaSegmentSyncStatus.SegmentSyncState.syncFailBtle;
            stravaSegmentSyncStatus.date = System.currentTimeMillis();
            StravaSegmentSyncStatus.saveSyncState(this.service, stravaSegmentSyncStatus);
        }
        BluetoothNavigationProgressReceiver.setTransmittingRouteFile(false);
        this.isDownloading = false;
        this.isListingFiles = false;
        return true;
    }

    @Override // android.bluetooth.BluetoothGattCallback
    public void onCharacteristicChanged(BluetoothGatt bluetoothGatt, BluetoothGattCharacteristic bluetoothGattCharacteristic) {
        Integer intValue;
        int iIntValue;
        if (this.service.bluetoothGatt != bluetoothGatt) {
            Log.i("Rides", "onCharacteristicChanged but for stale gatt instance, just using the stale instance");
        }
        if (transmitDataCharacteristic().equals(bluetoothGattCharacteristic.getUuid())) {
            final byte[] value = bluetoothGattCharacteristic.getValue();
            this.service.taskHandler.post(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.17
                @Override // java.lang.Runnable
                public void run() throws IOException {
                    LezyneCycleComputerDevice.this.onDataAvailable(value);
                }
            });
        }
        if (!bluetoothGattCharacteristic.getUuid().equals(LOCATION_AND_SPEED) || this.liveSessionSamples == null) {
            return;
        }
        Runnable runnable = this.postRouteSendingComplete;
        if (runnable != null) {
            this.postRouteSendingComplete = null;
            this.service.taskHandler.post(runnable);
        }
        Runnable runnable2 = this.postMapSendingComplete;
        if (runnable2 != null) {
            this.postMapSendingComplete = null;
            this.service.taskHandler.post(runnable2);
        }
        synchronized (this.liveSessionSamples) {
            BluetoothLeService.liveTrackLocationPacketCount++;
            LezyneLocationManager.INSTANCE.getInstance(this.service.getApplicationContext());
            byte[] value2 = bluetoothGattCharacteristic.getValue();
            boolean zTestBit = testBit(value2[0], 0);
            boolean zTestBit2 = testBit(value2[0], 1);
            boolean zTestBit3 = testBit(value2[0], 6);
            int i = 2;
            if (zTestBit) {
                intValue = bluetoothGattCharacteristic.getIntValue(18, 2);
                i = 4;
            } else {
                intValue = null;
            }
            if (zTestBit2) {
                iIntValue = bluetoothGattCharacteristic.getIntValue(20, i).intValue() & 16777215;
                i += 3;
            } else {
                iIntValue = 0;
            }
            Integer intValue2 = bluetoothGattCharacteristic.getIntValue(36, i);
            Integer intValue3 = bluetoothGattCharacteristic.getIntValue(36, i + 4);
            int i2 = i + 8;
            if (intValue2.intValue() != 0 && intValue3.intValue() != 0) {
                LezyneLocationManager.INSTANCE.getInstance(this.service).postLocation(intValue2.intValue(), intValue3.intValue());
            }
            Integer intValue4 = zTestBit3 ? bluetoothGattCharacteristic.getIntValue(36, i2) : null;
            if ((this.liveSessionState == LiveSessionState.start || this.liveSessionState == LiveSessionState.resume) && ((intValue2.intValue() != 0 && intValue3.intValue() != 0) || intValue4 != null)) {
                if (this.liveSessionSamples == null) {
                    this.liveSessionSamples = new HashMap<>();
                    this.lastLiveSessionSampleSize = 0;
                }
                synchronized (this.liveSessionSamples) {
                    LiveSessionSample liveSessionSample = this.liveSessionSamples.get(intValue4);
                    if (liveSessionSample == null) {
                        liveSessionSample = new LiveSessionSample();
                    }
                    liveSessionSample.latitude = intValue2.intValue() / 1.0E7f;
                    liveSessionSample.longitude = intValue3.intValue() / 1.0E7f;
                    liveSessionSample.timestamp = intValue4.intValue();
                    liveSessionSample.distance = iIntValue;
                    liveSessionSample.speed = intValue.intValue();
                    this.liveSessionSamples.put(intValue4, liveSessionSample);
                }
            }
        }
    }

    private void postMessageBody(OutgoingCommands outgoingCommands, OutgoingCommands outgoingCommands2, CharSequence charSequence) {
        byte[] bytes = charSequence.toString().getBytes(Charset.forName(CharEncoding.UTF_8));
        int length = bytes.length;
        if (length > 149) {
            length = 149;
        }
        byte[] bArr = new byte[20];
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byteBufferWrap.put(outgoingCommands.byteValue());
        byteBufferWrap.put((byte) (length & 255));
        int i = 18;
        int i2 = 0;
        while (i2 < length) {
            int i3 = length - i2;
            if (i3 < i) {
                i = i3;
            }
            byteBufferWrap.put(bytes, i2, i);
            this.outgoingMessageQue.add(bArr);
            i2 += i;
            bArr = new byte[20];
            byteBufferWrap = ByteBuffer.wrap(bArr);
            byteBufferWrap.put(outgoingCommands2.byteValue());
            i = 19;
        }
        postMessageQue();
    }

    public void postNotification(final NotificationMessageType notificationMessageType, final CharSequence charSequence, final CharSequence charSequence2) {
        if (this.outgoingMessageQue.size() > 1) {
            int i = this.postNotificationRetries;
            if (i < 12) {
                this.postNotificationRetries = i + 1;
                this.service.taskHandler.postDelayed(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.18
                    @Override // java.lang.Runnable
                    public void run() {
                        LezyneCycleComputerDevice.this.postNotification(notificationMessageType, charSequence, charSequence2);
                    }
                }, CoroutineLiveDataKt.DEFAULT_TIMEOUT);
                return;
            }
            return;
        }
        this.postNotificationRetries = 0;
        byte[] bArr = new byte[20];
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byte[] bytes = charSequence.toString().getBytes(Charset.forName(CharEncoding.UTF_8));
        if (bytes.length > 18) {
            bytes[18] = 0;
        }
        int length = bytes.length < 19 ? bytes.length : 19;
        int i2 = AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$NotificationMessageType[notificationMessageType.ordinal()];
        if (i2 == 1) {
            byteBufferWrap.put(OutgoingCommands.CallNotification.byteValue());
            byte[] bytes2 = charSequence2.toString().getBytes(Charset.forName(CharEncoding.UTF_8));
            int length2 = bytes2.length;
            byteBufferWrap.put(bytes2, 0, length2 <= 19 ? length2 : 19);
            this.outgoingMessageQue.add(bArr);
            postMessageQue();
            return;
        }
        if (i2 == 2) {
            byteBufferWrap.put(OutgoingCommands.EmailNotification.byteValue());
            int length3 = bytes.length;
            byteBufferWrap.put(bytes, 0, length3 <= 19 ? length3 : 19);
            this.outgoingMessageQue.add(bArr);
            postMessageBody(OutgoingCommands.EmailNotificationBody, OutgoingCommands.EmailNotificationNext, charSequence2);
            return;
        }
        if (i2 == 3) {
            byteBufferWrap.put(OutgoingCommands.SMSNotification.byteValue());
            byteBufferWrap.put(bytes, 0, length);
            this.outgoingMessageQue.add(bArr);
            postMessageBody(OutgoingCommands.SMSNotificationBody, OutgoingCommands.SMSNotificationNext, charSequence2);
            return;
        }
        if (i2 != 4) {
            return;
        }
        byteBufferWrap.put(OutgoingCommands.Notification.byteValue());
        int length4 = bytes.length;
        byteBufferWrap.put(bytes, 0, length4 <= 19 ? length4 : 19);
        this.outgoingMessageQue.add(bArr);
        postMessageBody(OutgoingCommands.NotificationBody, OutgoingCommands.NotificationNext, charSequence2);
    }

    public boolean canHandleNotifications() {
        return (this.currentConnectionState.dataState == DataState.CONNECTED_SLOW_DATA || this.currentConnectionState.dataState == DataState.WAITING) && this.currentConnectionState.gattState == GattState.CONNECTED;
    }

    void requestSettings(SettingsParser.SettingCategory[] settingCategoryArr) {
        Log.i("Rides", "Device requestSettingsFitFile " + settingCategoryArr.toString());
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(newPacket());
        byteBufferWrap.put(OutgoingCommands.SettingsRequest.byteValue());
        for (SettingsParser.SettingCategory settingCategory : settingCategoryArr) {
            byteBufferWrap.put(settingCategory.byteValue());
        }
        this.outgoingMessageQue.add(byteBufferWrap.array());
        postMessageQue();
    }

    void appendSettingsInput(ByteBuffer byteBuffer) {
        int length = byteBuffer.array().length - 1;
        int iPosition = this.settingsInputSize - this.settingsInput.position();
        if (iPosition <= length) {
            length = iPosition;
        }
        this.settingsInput.put(byteBuffer.array(), 1, length);
        if (this.settingsInputSize <= this.settingsInput.position()) {
            this.service.onSettingsFileDownloaded(this.settingsInput, this.settingsInputSize);
        }
    }

    void writeSettings(ByteBuffer byteBuffer) {
        int i;
        int iPosition = byteBuffer.position();
        int iPosition2 = byteBuffer.position();
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(newPacket());
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.put(OutgoingCommands.UpdateSetting.byteValue());
        byteBufferWrap.putShort((short) iPosition2);
        if (iPosition2 >= 17) {
            byteBufferWrap.put(byteBuffer.array(), 0, 17);
            i = iPosition - 17;
            this.outgoingMessageQue.add(byteBufferWrap.array());
            iPosition2 = 17;
        } else {
            byteBufferWrap.put(byteBuffer.array(), 0, iPosition2);
            i = iPosition - iPosition2;
            this.outgoingMessageQue.add(byteBufferWrap.array());
        }
        while (i > 0) {
            ByteBuffer byteBufferWrap2 = ByteBuffer.wrap(newPacket());
            byteBufferWrap2.put(OutgoingCommands.UpdateSettingContinue.byteValue());
            if (i >= 19) {
                byteBufferWrap2.put(byteBuffer.array(), iPosition2, 19);
                this.outgoingMessageQue.add(byteBufferWrap2.array());
                iPosition2 += 19;
                i -= 19;
            } else {
                byteBufferWrap2.put(byteBuffer.array(), iPosition2, i);
                this.outgoingMessageQue.add(byteBufferWrap2.array());
                iPosition2 += i;
                i = 0;
            }
        }
        postMessageQue();
    }

    public int sendTrainingFile(byte[] bArr, int i) {
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(newPacket());
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferWrap.put(OutgoingCommands.TrainingFileUploadStart.byteValue());
        byteBufferWrap.putShort((short) i);
        this.outgoingMessageQue.add(byteBufferWrap.array());
        int i2 = 0;
        int i3 = 1;
        while (i2 < i) {
            ByteBuffer byteBufferWrap2 = ByteBuffer.wrap(newPacket());
            byteBufferWrap2.order(ByteOrder.LITTLE_ENDIAN);
            int i4 = i - i2;
            if (i4 <= 19) {
                byteBufferWrap2.put(OutgoingCommands.TrainingFileUploadEnd.byteValue());
                byteBufferWrap2.put(bArr, i2, i4);
                i2 += i4;
                this.outgoingMessageQue.add(byteBufferWrap2.array());
            } else {
                byteBufferWrap2.put(OutgoingCommands.TrainingFileUploadData.byteValue());
                byteBufferWrap2.put(bArr, i2, 19);
                i2 += 19;
                this.outgoingMessageQue.add(byteBufferWrap2.array());
            }
            i3++;
        }
        postMessageQue();
        return i3;
    }

    public void onBluetoothBonded() {
        synchronized (this.service) {
            Log.i("Rides", " currentConnectionState.bondState = BondState.BONDED ");
            if (this.currentConnectionState.gattState == GattState.CONNECTED && this.service.currentDevice == this) {
                this.service.onConnect();
                this.service.Log("We bonded after the serviced were discovered. Connected!");
            }
        }
    }

    public void onAclConnected(BluetoothDevice bluetoothDevice) {
        Log.i(HttpHeaders.CONNECTION, "onAclConnected ");
        if (this.currentConnectionState.gattState == GattState.DISCONNECTED) {
            Log.i("Rides", "Calling connect because of onAclConnected");
            connect(bluetoothDevice);
        }
    }

    ArrayList<BleFitFile> currentDeviceFiles() {
        return this.currentFileList;
    }

    public enum OutgoingCommands {
        InvalidCommand(0),
        RequestFitFileList(1),
        RequestFitFileDownload(2),
        RequestFitFileDelete(3),
        NewSegmentListReady(4),
        EmailNotification(5),
        EmailNotificationBody(6),
        EmailNotificationNext(7),
        SMSNotification(8),
        SMSNotificationBody(9),
        SMSNotificationNext(10),
        CallNotification(11),
        RequestSlowDownloads(12),
        NavigationNewRoute(13),
        NavigationRouteDataContinue(14),
        NavigationStep(15),
        NavigationStepContinued(16),
        NavigationRouteData(17),
        SegmentListItem(18),
        SegmentListItemDone(19),
        SegmentFileUploadStart(20),
        SegmentFileUploadData(21),
        SegmentFileUploadEnd(22),
        PhoneStatus(25),
        SegmentUpdateCancel(26),
        NavigationError(27),
        NavigationNewDestination(29),
        NavigationNewFile(30),
        NavigationNewFileDest(31),
        NavFileUploadDataStart(32),
        NavFileUploadData(33),
        NavFileUploadEnd(34),
        NavigationPhoneCancel_V2(35),
        SettingsRequest(36),
        UpdateSetting(37),
        UpdateSettingContinue(38),
        Notification(39),
        NotificationBody(40),
        NotificationNext(41),
        TrainingFileUploadStart(42),
        TrainingFileUploadData(43),
        TrainingFileUploadEnd(44),
        MapFileReadyStart(45),
        MapFileReadyEnd(46),
        MapFileStart(47),
        MapFileData(48),
        MapFileEnd(49),
        MapFileError(50),
        MapFileListRequest(51),
        MapFileDelete(52);

        public int value;

        OutgoingCommands(int i) {
            this.value = i;
        }

        public byte byteValue() {
            return (byte) this.value;
        }

        public static OutgoingCommands fromByte(byte b) {
            for (OutgoingCommands outgoingCommands : values()) {
                if (outgoingCommands.byteValue() == b) {
                    return outgoingCommands;
                }
            }
            return null;
        }
    }

    public enum IncomingCommands {
        InvalidCommand(0),
        FitFileTransferStart(1),
        FitFileTransferData(2),
        FitFileTransferEnd(3),
        SwitchingToHighSpeed(4),
        ConnectedInHighSpeed(5),
        SwitchingToLowSpeed(6),
        ConnectedInLowSpeed(7),
        DebugText(8),
        ErrorPacket(9),
        FileDeleteConfirmation(10),
        FileListSending(11),
        NavigationRerouteRequest(12),
        LiveSensorData(13),
        LiveSessionStatus(14),
        GPSReadyToReceiveSegmentList(15),
        RequestPhoneStatus(16),
        SegmentFileRequest(17),
        SegmentFileRequestEnd(18),
        NavigationNewFileReady(20),
        SettingsSendStart(22),
        NavigationGPSCancel(23),
        SettingsSendData(24),
        SettingsSendError(25),
        TrainingSendError(27),
        MapFileReq(28),
        MapFileError(29),
        RequestMTUUpdate(30),
        MapFileSizeError(31),
        MapFileListData(32),
        MapFileListEnd(33),
        MapFileDeleteComplete(34),
        MapFileDeleteError(35),
        MapFileListError(36),
        NavigationFailed(37);

        public int value;

        public byte byteValue() {
            return (byte) this.value;
        }

        IncomingCommands(int i) {
            this.value = i;
        }

        public static IncomingCommands fromByte(byte b) {
            for (IncomingCommands incomingCommands : values()) {
                if (incomingCommands.byteValue() == b) {
                    return incomingCommands;
                }
            }
            return null;
        }
    }

    public enum LiveSessionState {
        end(0),
        start(1),
        pause(2),
        resume(3),
        invalid(4);

        public int value;

        LiveSessionState(int i) {
            this.value = i;
        }

        public byte byteValue() {
            return (byte) this.value;
        }

        public static LiveSessionState fromByte(byte b) {
            for (LiveSessionState liveSessionState : values()) {
                if (liveSessionState.byteValue() == b) {
                    return liveSessionState;
                }
            }
            return null;
        }
    }

    public class ConnectionState {
        public GattState gattState = GattState.DISCONNECTED;
        public DataState dataState = DataState.DISCONNECTED;
        public LocationServiceState locationServiceState = LocationServiceState.DISCONNECTED;

        public ConnectionState() {
        }
    }

    boolean isBonded() {
        BluetoothDevice bluetoothDevice = this.bluetoothDevice;
        if ((bluetoothDevice != null ? bluetoothDevice.getBondState() : 0) == 12) {
            return true;
        }
        Iterator<BluetoothDevice> it = this.service.bluetoothAdapter.getBondedDevices().iterator();
        while (it.hasNext()) {
            if (this.bluetoothDevice.getAddress().equalsIgnoreCase(it.next().getAddress())) {
                return true;
            }
        }
        return false;
    }

    boolean isConnected() {
        if (this.currentConnectionState.gattState == GattState.CONNECTED) {
            return true;
        }
        logConnectionState();
        return false;
    }

    public LezyneCycleComputerDevice(BluetoothLeService bluetoothLeService) {
        instanceCount++;
        Log.i("Rides", " $$ Constructor called for bluetooth device " + instanceCount);
        this.service = bluetoothLeService;
        this.routeCreator = NavigationRouteCreator.instance(bluetoothLeService.getApplicationContext());
    }

    public void connect(final BluetoothDevice bluetoothDevice) {
        this.service.taskHandler.removeCallbacks(this.connectTimeoutRunnable);
        if (SystemClock.elapsedRealtime() - this.tryingToConnectTime < 1000) {
            Log.i("Rides", "BluetoothDevice::Connect called  -- IGNORED " + (SystemClock.elapsedRealtime() - this.tryingToConnectTime));
            return;
        }
        Log.i("Rides", "BluetoothDevice::Connect called");
        this.tryingToConnectTime = SystemClock.elapsedRealtime();
        this.service.taskHandler.removeCallbacks(this.discoverServicesTimeoutRunnable);
        this.service.taskHandler.removeCallbacks(this.discoverServicesDelayedTask);
        this.calledDiscoverServicedTime = 0L;
        this.service.taskHandler.post(new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.20
            @Override // java.lang.Runnable
            public void run() {
                LezyneCycleComputerDevice.this.needToSubscribeToLocationUpdates = true;
                LezyneCycleComputerDevice.this.alreadySubscribedToLocationUpdates = false;
                LezyneCycleComputerDevice.this.currentConnectionState.gattState = GattState.TRYING_TO_CONNECT;
                LezyneCycleComputerDevice.this.service.taskHandler.postDelayed(LezyneCycleComputerDevice.this.connectTimeoutRunnable, 45000L);
                Log.i("Rides", "currentConnectionState.gattState = GattState.TRYING_TO_CONNECT; " + LezyneCycleComputerDevice.instanceCount);
                if (LezyneCycleComputerDevice.this.service.bluetoothGatt != null && bluetoothDevice != null && LezyneCycleComputerDevice.this.service.lastConnectedAddress().trim().length() > 0 && bluetoothDevice.getAddress().equalsIgnoreCase(LezyneCycleComputerDevice.this.service.bluetoothGatt.getDevice().getAddress())) {
                    Log.i(HttpHeaders.CONNECTION, "Connecting to last device");
                    BluetoothConnectionStateListener.broadcastConnectingStatus(LezyneCycleComputerDevice.this.service, BluetoothConnectionStateListener.ConnectingStatus.ConnectingBluetooth, bluetoothDevice.getName(), 10000L);
                    if (LezyneCycleComputerDevice.this.service.bluetoothGatt == null || !LezyneCycleComputerDevice.this.service.bluetoothGatt.connect()) {
                        LezyneCycleComputerDevice.this.service.bluetoothGatt = bluetoothDevice.connectGatt(LezyneCycleComputerDevice.this.service, false, LezyneCycleComputerDevice.this, 2);
                    }
                } else {
                    Log.i(HttpHeaders.CONNECTION, "BaseBluetoothDevice::Connecting new device " + bluetoothDevice.getName());
                    LezyneCycleComputerDevice.this.service.bluetoothGatt = bluetoothDevice.connectGatt(LezyneCycleComputerDevice.this.service, false, LezyneCycleComputerDevice.this);
                    LezyneCycleComputerDevice.this.connectGattInitiateTime = SystemClock.elapsedRealtime();
                }
                LezyneCycleComputerDevice.this.bluetoothDevice = bluetoothDevice;
                LezyneCycleComputerDevice.this.address = bluetoothDevice.getAddress();
            }
        });
    }

    public String getAddress() {
        BluetoothDevice bluetoothDevice = this.bluetoothDevice;
        return bluetoothDevice == null ? "" : bluetoothDevice.getAddress();
    }

    /* JADX WARN: Removed duplicated region for block: B:47:0x017e  */
    /* JADX WARN: Removed duplicated region for block: B:58:0x01e7  */
    /* JADX WARN: Removed duplicated region for block: B:60:0x01eb  */
    /* JADX WARN: Removed duplicated region for block: B:62:0x01f4  */
    /* JADX WARN: Removed duplicated region for block: B:63:0x0203  */
    @Override // android.bluetooth.BluetoothGattCallback
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct code enable 'Show inconsistent code' option in preferences
    */
    public void onConnectionStateChange(android.bluetooth.BluetoothGatt r13, int r14, int r15) throws java.io.IOException {
        /*
            Method dump skipped, instructions count: 541
            To view this dump change 'Code comments level' option to 'DEBUG'
        */
        throw new UnsupportedOperationException("Method not decompiled: com.lezyne.gpsally.services.LezyneCycleComputerDevice.onConnectionStateChange(android.bluetooth.BluetoothGatt, int, int):void");
    }

    /* JADX INFO: Access modifiers changed from: private */
    public /* synthetic */ void lambda$onConnectionStateChange$0() {
        this.tryingToConnectTime = 0L;
        this.service.connect(this.bluetoothDevice);
    }

    public enum GpsDeviceModel {
        InvalidDevice,
        Y9Mini,
        Y9Power,
        Y9Super,
        Y10Super,
        Y10Macro,
        Y10Micro,
        Y10MicroColor,
        Y10MicroWatch,
        Y10WatchColor,
        Y10Mini,
        Y12Mega,
        Y12MegaColor,
        Y13Super,
        Y13Macro;

        public static GpsDeviceModel fromInt(int i) {
            if (i > 60) {
                i -= 60;
            }
            switch (i) {
                case 1:
                    return Y9Mini;
                case 2:
                    return Y9Power;
                case 3:
                    return Y9Super;
                case 4:
                    return Y10Super;
                case 5:
                    return Y10Macro;
                case 6:
                    return Y10Micro;
                case 7:
                    return Y10MicroColor;
                case 8:
                    return Y10MicroWatch;
                case 9:
                    return Y10WatchColor;
                case 10:
                    return Y10Mini;
                case 11:
                    return Y12Mega;
                case 12:
                    return Y12MegaColor;
                case 13:
                    return Y13Super;
                case 14:
                    return Y13Macro;
                default:
                    return InvalidDevice;
            }
        }
    }

    public static class GpsDeviceInfo {
        public int bleSpeed;
        public int freescaleMajorVersion = 0;
        public int freescaleMinorVersion = 0;
        int gpsMode;
        public boolean isJapaneese;
        public boolean isNavigating;
        public boolean isRecording;
        public int majorVer;
        public int minorVer;
        public GpsDeviceModel model;
        public int verRev;

        public GpsDeviceInfo(SettingsParser settingsParser) {
            setModelFromSettings(settingsParser);
        }

        public GpsDeviceInfo() {
        }

        public boolean supportsMaps() {
            return this.model == GpsDeviceModel.Y12Mega || this.model == GpsDeviceModel.Y12MegaColor || this.model == GpsDeviceModel.Y13Super;
        }

        public boolean supportsLandscape() {
            return this.model == GpsDeviceModel.Y12Mega || this.model == GpsDeviceModel.Y13Super || this.model == GpsDeviceModel.Y13Macro;
        }

        public void setModelFromSettings(SettingsParser settingsParser) {
            byte b = settingsParser.systemConstants.ModeGPS_Model;
            if (b > 60) {
                this.isJapaneese = true;
                b = (byte) (b - 60);
            } else {
                this.isJapaneese = false;
            }
            switch (b) {
                case 1:
                    this.model = GpsDeviceModel.Y9Mini;
                    break;
                case 2:
                    this.model = GpsDeviceModel.Y9Power;
                    break;
                case 3:
                    this.model = GpsDeviceModel.Y9Super;
                    break;
                case 4:
                    this.model = GpsDeviceModel.Y10Super;
                    break;
                case 5:
                    this.model = GpsDeviceModel.Y10Macro;
                    break;
                case 6:
                    this.model = GpsDeviceModel.Y10Micro;
                    break;
                case 7:
                    this.model = GpsDeviceModel.Y10MicroColor;
                    break;
                case 8:
                    this.model = GpsDeviceModel.Y10MicroWatch;
                    break;
                case 9:
                    this.model = GpsDeviceModel.Y10WatchColor;
                    break;
                case 10:
                    this.model = GpsDeviceModel.Y10Mini;
                    break;
                case 11:
                    this.model = GpsDeviceModel.Y12Mega;
                    break;
                case 12:
                    this.model = GpsDeviceModel.Y12MegaColor;
                    break;
                case 13:
                    this.model = GpsDeviceModel.Y13Super;
                    break;
                case 14:
                    this.model = GpsDeviceModel.Y13Macro;
                    break;
            }
        }

        /* JADX WARN: Removed duplicated region for block: B:21:0x003c  */
        /*
            Code decompiled incorrectly, please refer to instructions dump.
            To view partially-correct code enable 'Show inconsistent code' option in preferences
        */
        public java.lang.String deviceName() {
            /*
                r2 = this;
                com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceModel r0 = r2.model
                if (r0 == 0) goto L3c
                int[] r0 = com.lezyne.gpsally.services.LezyneCycleComputerDevice.AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel
                com.lezyne.gpsally.services.LezyneCycleComputerDevice$GpsDeviceModel r1 = r2.model
                int r1 = r1.ordinal()
                r0 = r0[r1]
                switch(r0) {
                    case 2: goto L39;
                    case 3: goto L36;
                    case 4: goto L33;
                    case 5: goto L30;
                    case 6: goto L2d;
                    case 7: goto L2a;
                    case 8: goto L27;
                    case 9: goto L24;
                    case 10: goto L21;
                    case 11: goto L1e;
                    case 12: goto L1b;
                    case 13: goto L18;
                    case 14: goto L15;
                    case 15: goto L12;
                    default: goto L11;
                }
            L11:
                goto L3c
            L12:
                java.lang.String r0 = "Y13Macro"
                goto L3e
            L15:
                java.lang.String r0 = "Y13Super"
                goto L3e
            L18:
                java.lang.String r0 = "Y12MegaColor"
                goto L3e
            L1b:
                java.lang.String r0 = "Y12Mega"
                goto L3e
            L1e:
                java.lang.String r0 = "Y10Mini"
                goto L3e
            L21:
                java.lang.String r0 = "Y10WatchColor"
                goto L3e
            L24:
                java.lang.String r0 = "Y10MicroWatch"
                goto L3e
            L27:
                java.lang.String r0 = "Y10MicroColor"
                goto L3e
            L2a:
                java.lang.String r0 = "Y10Micro"
                goto L3e
            L2d:
                java.lang.String r0 = "Y10Macro"
                goto L3e
            L30:
                java.lang.String r0 = "Y10Super"
                goto L3e
            L33:
                java.lang.String r0 = "Y9Super"
                goto L3e
            L36:
                java.lang.String r0 = "Y9Power"
                goto L3e
            L39:
                java.lang.String r0 = "Y9Mini"
                goto L3e
            L3c:
                java.lang.String r0 = ""
            L3e:
                java.lang.StringBuilder r1 = new java.lang.StringBuilder
                r1.<init>()
                java.lang.StringBuilder r0 = r1.append(r0)
                java.lang.String r1 = "_"
                java.lang.StringBuilder r0 = r0.append(r1)
                int r1 = r2.majorVer
                java.lang.StringBuilder r0 = r0.append(r1)
                java.lang.String r1 = "."
                java.lang.StringBuilder r0 = r0.append(r1)
                int r1 = r2.minorVer
                java.lang.StringBuilder r0 = r0.append(r1)
                java.lang.String r0 = r0.toString()
                return r0
            */
            throw new UnsupportedOperationException("Method not decompiled: com.lezyne.gpsally.services.LezyneCycleComputerDevice.GpsDeviceInfo.deviceName():java.lang.String");
        }
    }

    @Override // android.bluetooth.BluetoothGattCallback
    public void onServicesDiscovered(BluetoothGatt bluetoothGatt, int i) {
        this.statusPacketCounter = 0;
        this.service.Log("onServicedDiscovered status=" + i + "    isNewGatt  " + (bluetoothGatt == this.service.bluetoothGatt ? "same gatt" : "new gatt"));
        this.service.taskHandler.removeCallbacks(this.service.autoConnectPolling);
        this.service.taskHandler.postDelayed(this.service.autoConnectPolling, 10000L);
        this.service.taskHandler.removeCallbacks(this.discoverServicesTimeoutRunnable);
        if (i == 0) {
            new Settings(this.service).setNoLongerNeedsPowerCycle();
            onServicesDiscovered(bluetoothGatt);
            this.gattConnectionTime = SystemClock.elapsedRealtime();
        } else {
            Log.e("SCAN", "Bluetooth LE Service GATT error status =" + i);
            this.service.settings.clearPositiveUserEventCount();
            this.currentConnectionState.gattState = GattState.DISCONNECTED;
        }
    }

    void postMessageQue() {
        this.service.taskHandler.removeCallbacks(this.postMessageQueueRetryTask);
        synchronized (this.outgoingMessageQue) {
            if (this.blockMessageQueue) {
                if (SystemClock.elapsedRealtime() - this.blockMessageQueueTime > 10000) {
                    this.blockMessageQueue = false;
                } else {
                    this.service.taskHandler.postDelayed(this.postMessageQueueRetryTask, 1000L);
                    return;
                }
            }
            long jElapsedRealtime = SystemClock.elapsedRealtime();
            long j = this.postMessageQueBlockedUntil;
            if (jElapsedRealtime < j) {
                this.service.taskHandler.postDelayed(this.postMessageQueueRetryTask, j - SystemClock.elapsedRealtime());
                return;
            }
            if (this.isSendingToBluetoothDevice) {
                this.service.taskHandler.postDelayed(this.postMessageQueueRetryTask, 100L);
                Log.i("BTLE", "isSendingToBluetoothDevice  is true so we return ");
                return;
            }
            if (!isConnected()) {
                this.service.taskHandler.postDelayed(this.postMessageQueueRetryTask, 500L);
                return;
            }
            if (this.outgoingMessageQue.size() > 0) {
                this.isSendingToBluetoothDevice = true;
                if (this.outgoingMessageQue.size() != 0) {
                    byte[] bArr = this.outgoingMessageQue.get(0);
                    if (bArr.length > 20) {
                        this.postMessageQueBlockedUntil = 0L;
                    } else {
                        this.postMessageQueBlockedUntil = SystemClock.elapsedRealtime() + 20;
                    }
                    int i = AnonymousClass31.$SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$WriteRxCharacteristicResult[sendDataAsRxCharacteristic(bArr).ordinal()];
                    if (i == 1) {
                        Log.i("BtleBytes", "---> " + OutgoingCommands.fromByte(bArr[0]) + "\t" + StringTool.toHex(bArr));
                        this.outgoingMessageQue.remove(0);
                    } else if (i == 2) {
                        Log.i("BtleBytes", "---> ERROR SEND" + OutgoingCommands.fromByte(bArr[0]) + "\t" + StringTool.toHex(bArr));
                        this.postMessageQueBlockedUntil = SystemClock.elapsedRealtime() + 250;
                    } else if (i == 3) {
                        Log.i("BtleBytes", "---> ERROR SEND" + OutgoingCommands.fromByte(bArr[0]) + "\t" + StringTool.toHex(bArr));
                        this.postMessageQueBlockedUntil = SystemClock.elapsedRealtime() + 2500;
                    }
                }
            }
            this.isSendingToBluetoothDevice = false;
        }
    }

    /* renamed from: com.lezyne.gpsally.services.LezyneCycleComputerDevice$31, reason: invalid class name */
    static /* synthetic */ class AnonymousClass31 {
        static final /* synthetic */ int[] $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands;
        static final /* synthetic */ int[] $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState;
        static final /* synthetic */ int[] $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$WriteRxCharacteristicResult;
        static final /* synthetic */ int[] $SwitchMap$com$lezyne$gpsally$services$NotificationMessageType;
        static final /* synthetic */ int[] $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider;

        static {
            int[] iArr = new int[WriteRxCharacteristicResult.values().length];
            $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$WriteRxCharacteristicResult = iArr;
            try {
                iArr[WriteRxCharacteristicResult.success.ordinal()] = 1;
            } catch (NoSuchFieldError unused) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$WriteRxCharacteristicResult[WriteRxCharacteristicResult.failNoRecovery.ordinal()] = 2;
            } catch (NoSuchFieldError unused2) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$WriteRxCharacteristicResult[WriteRxCharacteristicResult.failWithRecovery.ordinal()] = 3;
            } catch (NoSuchFieldError unused3) {
            }
            int[] iArr2 = new int[NotificationMessageType.values().length];
            $SwitchMap$com$lezyne$gpsally$services$NotificationMessageType = iArr2;
            try {
                iArr2[NotificationMessageType.call.ordinal()] = 1;
            } catch (NoSuchFieldError unused4) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$NotificationMessageType[NotificationMessageType.email.ordinal()] = 2;
            } catch (NoSuchFieldError unused5) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$NotificationMessageType[NotificationMessageType.sms.ordinal()] = 3;
            } catch (NoSuchFieldError unused6) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$NotificationMessageType[NotificationMessageType.other.ordinal()] = 4;
            } catch (NoSuchFieldError unused7) {
            }
            int[] iArr3 = new int[RoutingProfile.RoutingProvider.values().length];
            $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider = iArr3;
            try {
                iArr3[RoutingProfile.RoutingProvider.gpsRoot_providerA.ordinal()] = 1;
            } catch (NoSuchFieldError unused8) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.gpsRoot_providerB.ordinal()] = 2;
            } catch (NoSuchFieldError unused9) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.gpsRoot_providerC.ordinal()] = 3;
            } catch (NoSuchFieldError unused10) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.gpsRoot_providerD.ordinal()] = 4;
            } catch (NoSuchFieldError unused11) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.MountainBike.ordinal()] = 5;
            } catch (NoSuchFieldError unused12) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.RoadBike.ordinal()] = 6;
            } catch (NoSuchFieldError unused13) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.EazyRide.ordinal()] = 7;
            } catch (NoSuchFieldError unused14) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.Shortest.ordinal()] = 8;
            } catch (NoSuchFieldError unused15) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.Hiking.ordinal()] = 9;
            } catch (NoSuchFieldError unused16) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.Commuter.ordinal()] = 10;
            } catch (NoSuchFieldError unused17) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$tools$RoutingProfile$RoutingProvider[RoutingProfile.RoutingProvider.Custom.ordinal()] = 11;
            } catch (NoSuchFieldError unused18) {
            }
            int[] iArr4 = new int[GpsDeviceModel.values().length];
            $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel = iArr4;
            try {
                iArr4[GpsDeviceModel.InvalidDevice.ordinal()] = 1;
            } catch (NoSuchFieldError unused19) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y9Mini.ordinal()] = 2;
            } catch (NoSuchFieldError unused20) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y9Power.ordinal()] = 3;
            } catch (NoSuchFieldError unused21) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y9Super.ordinal()] = 4;
            } catch (NoSuchFieldError unused22) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10Super.ordinal()] = 5;
            } catch (NoSuchFieldError unused23) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10Macro.ordinal()] = 6;
            } catch (NoSuchFieldError unused24) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10Micro.ordinal()] = 7;
            } catch (NoSuchFieldError unused25) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10MicroColor.ordinal()] = 8;
            } catch (NoSuchFieldError unused26) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10MicroWatch.ordinal()] = 9;
            } catch (NoSuchFieldError unused27) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10WatchColor.ordinal()] = 10;
            } catch (NoSuchFieldError unused28) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y10Mini.ordinal()] = 11;
            } catch (NoSuchFieldError unused29) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y12Mega.ordinal()] = 12;
            } catch (NoSuchFieldError unused30) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y12MegaColor.ordinal()] = 13;
            } catch (NoSuchFieldError unused31) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y13Super.ordinal()] = 14;
            } catch (NoSuchFieldError unused32) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$GpsDeviceModel[GpsDeviceModel.Y13Macro.ordinal()] = 15;
            } catch (NoSuchFieldError unused33) {
            }
            int[] iArr5 = new int[LiveSessionState.values().length];
            $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState = iArr5;
            try {
                iArr5[LiveSessionState.invalid.ordinal()] = 1;
            } catch (NoSuchFieldError unused34) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[LiveSessionState.end.ordinal()] = 2;
            } catch (NoSuchFieldError unused35) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[LiveSessionState.resume.ordinal()] = 3;
            } catch (NoSuchFieldError unused36) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[LiveSessionState.start.ordinal()] = 4;
            } catch (NoSuchFieldError unused37) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$LiveSessionState[LiveSessionState.pause.ordinal()] = 5;
            } catch (NoSuchFieldError unused38) {
            }
            int[] iArr6 = new int[IncomingCommands.values().length];
            $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands = iArr6;
            try {
                iArr6[IncomingCommands.TrainingSendError.ordinal()] = 1;
            } catch (NoSuchFieldError unused39) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileSizeError.ordinal()] = 2;
            } catch (NoSuchFieldError unused40) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileListData.ordinal()] = 3;
            } catch (NoSuchFieldError unused41) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileListEnd.ordinal()] = 4;
            } catch (NoSuchFieldError unused42) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileListError.ordinal()] = 5;
            } catch (NoSuchFieldError unused43) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileDeleteComplete.ordinal()] = 6;
            } catch (NoSuchFieldError unused44) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileDeleteError.ordinal()] = 7;
            } catch (NoSuchFieldError unused45) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.RequestMTUUpdate.ordinal()] = 8;
            } catch (NoSuchFieldError unused46) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileReq.ordinal()] = 9;
            } catch (NoSuchFieldError unused47) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.MapFileError.ordinal()] = 10;
            } catch (NoSuchFieldError unused48) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.InvalidCommand.ordinal()] = 11;
            } catch (NoSuchFieldError unused49) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.FitFileTransferStart.ordinal()] = 12;
            } catch (NoSuchFieldError unused50) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.FitFileTransferData.ordinal()] = 13;
            } catch (NoSuchFieldError unused51) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.FitFileTransferEnd.ordinal()] = 14;
            } catch (NoSuchFieldError unused52) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SwitchingToHighSpeed.ordinal()] = 15;
            } catch (NoSuchFieldError unused53) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.ConnectedInHighSpeed.ordinal()] = 16;
            } catch (NoSuchFieldError unused54) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SwitchingToLowSpeed.ordinal()] = 17;
            } catch (NoSuchFieldError unused55) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.ConnectedInLowSpeed.ordinal()] = 18;
            } catch (NoSuchFieldError unused56) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.DebugText.ordinal()] = 19;
            } catch (NoSuchFieldError unused57) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.ErrorPacket.ordinal()] = 20;
            } catch (NoSuchFieldError unused58) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.FileDeleteConfirmation.ordinal()] = 21;
            } catch (NoSuchFieldError unused59) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.FileListSending.ordinal()] = 22;
            } catch (NoSuchFieldError unused60) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.GPSReadyToReceiveSegmentList.ordinal()] = 23;
            } catch (NoSuchFieldError unused61) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SegmentFileRequest.ordinal()] = 24;
            } catch (NoSuchFieldError unused62) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SegmentFileRequestEnd.ordinal()] = 25;
            } catch (NoSuchFieldError unused63) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.RequestPhoneStatus.ordinal()] = 26;
            } catch (NoSuchFieldError unused64) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.NavigationGPSCancel.ordinal()] = 27;
            } catch (NoSuchFieldError unused65) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.NavigationFailed.ordinal()] = 28;
            } catch (NoSuchFieldError unused66) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.NavigationRerouteRequest.ordinal()] = 29;
            } catch (NoSuchFieldError unused67) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.LiveSensorData.ordinal()] = 30;
            } catch (NoSuchFieldError unused68) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.LiveSessionStatus.ordinal()] = 31;
            } catch (NoSuchFieldError unused69) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.NavigationNewFileReady.ordinal()] = 32;
            } catch (NoSuchFieldError unused70) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SettingsSendStart.ordinal()] = 33;
            } catch (NoSuchFieldError unused71) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SettingsSendData.ordinal()] = 34;
            } catch (NoSuchFieldError unused72) {
            }
            try {
                $SwitchMap$com$lezyne$gpsally$services$LezyneCycleComputerDevice$IncomingCommands[IncomingCommands.SettingsSendError.ordinal()] = 35;
            } catch (NoSuchFieldError unused73) {
            }
        }
    }

    @Override // android.bluetooth.BluetoothGattCallback
    public void onCharacteristicWrite(BluetoothGatt bluetoothGatt, BluetoothGattCharacteristic bluetoothGattCharacteristic, int i) {
        this.isSendingToBluetoothDevice = false;
        this.service.taskHandler.post(this.postMessageQueueRetryTask);
    }

    public boolean enableReceiveDataNotification() {
        BluetoothGattService service = this.service.bluetoothGatt.getService(lezyneDataService());
        if (service == null) {
            this.service.taskHandler.removeCallbacks(this.service.autoConnectPolling);
            this.service.taskHandler.postDelayed(this.service.autoConnectPolling, 20000L);
            this.service.bluetoothGatt.discoverServices();
            Log.e("BTLE", "Rx service not found! We need to determine how to handle this error");
            this.service.settings.clearPositiveUserEventCount();
            return false;
        }
        BluetoothGattCharacteristic characteristic = service.getCharacteristic(transmitDataCharacteristic());
        if (characteristic == null) {
            this.service.taskHandler.removeCallbacks(this.service.autoConnectPolling);
            this.service.taskHandler.postDelayed(this.service.autoConnectPolling, 20000L);
            this.service.bluetoothGatt.discoverServices();
            Log.e("BTLE", "Tx charateristic not found! We need to determine how to handle this error");
            this.service.settings.clearPositiveUserEventCount();
            return false;
        }
        this.service.bluetoothGatt.setCharacteristicNotification(characteristic, true);
        BluetoothGattDescriptor descriptor = characteristic.getDescriptor(CCCD);
        if (descriptor == null || this.service.bluetoothGatt == null) {
            Log.e("Rides", " TxCharicteristic descriptor is null, they probobly need to restart the phone");
            this.service.settings.needsPhonePowerCycle();
        } else {
            descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
            this.service.bluetoothGatt.writeDescriptor(descriptor);
            Log.i("Rides", "Wrote descriptor to enable data to be received");
            BluetoothConnectionStateListener.broadcastConnectingStatus(this.service, BluetoothConnectionStateListener.ConnectingStatus.ServicesConnected, this.bluetoothDevice.getName(), 10000L);
        }
        return true;
    }

    private WriteRxCharacteristicResult sendDataAsRxCharacteristic(byte[] bArr) {
        WriteRxCharacteristicResult writeRxCharacteristicResult = WriteRxCharacteristicResult.success;
        if (this.service.bluetoothGatt == null) {
            Log.e("BTLE", "Tried to sendDataAsRxCharacterstic but bluetoothGatt was null");
            return WriteRxCharacteristicResult.failWithRecovery;
        }
        BluetoothGattService service = this.service.bluetoothGatt.getService(lezyneDataService());
        if (service == null) {
            Log.e("BTLE", "Rx service not found!");
            this.service.bluetoothGatt.discoverServices();
            this.service.taskHandler.removeCallbacks(this.service.autoConnectPolling);
            this.service.taskHandler.postDelayed(this.service.autoConnectPolling, 10000L);
            Log.e("BTLE", "Resetting adapter too many rx get service fails");
            this.service.bluetoothGatt.close();
            BluetoothLeService bluetoothLeService = this.service;
            bluetoothLeService.bluetoothGatt = this.bluetoothDevice.connectGatt(bluetoothLeService, false, this, 2);
            this.service.settings.clearPositiveUserEventCount();
            return WriteRxCharacteristicResult.failWithRecovery;
        }
        try {
            BluetoothGattCharacteristic characteristic = service.getCharacteristic(receiveDataCharacteristic());
            if (characteristic == null) {
                Log.e("Rides", "Rx characteristic not found!");
                this.service.settings.clearPositiveUserEventCount();
                writeRxCharacteristicResult = WriteRxCharacteristicResult.failWithRecovery;
            }
            characteristic.setValue(bArr);
            if (!this.service.bluetoothGatt.writeCharacteristic(characteristic)) {
                badStatusCounter++;
                this.service.settings.clearPositiveUserEventCount();
                writeRxCharacteristicResult = WriteRxCharacteristicResult.failNoRecovery;
            } else {
                badStatusCounter = 0;
            }
            if (badStatusCounter <= 2) {
                return writeRxCharacteristicResult;
            }
            this.service.bluetoothGatt.close();
            this.service.settings.clearPositiveUserEventCount();
            BluetoothLeService bluetoothLeService2 = this.service;
            bluetoothLeService2.bluetoothGatt = this.bluetoothDevice.connectGatt(bluetoothLeService2, false, this, 2);
            return WriteRxCharacteristicResult.failWithRecovery;
        } catch (NullPointerException e) {
            e.printStackTrace();
            Log.e("Rides", "Error setting value on RxChar");
            return writeRxCharacteristicResult;
        }
    }

    protected void setTimeoutTimer(String str, int i) {
        this.timeoutSender = str;
        this.service.taskHandler.removeCallbacks(this.transferTimeoutAlarmRunnable);
        this.service.taskHandler.postDelayed(this.transferTimeoutAlarmRunnable, i);
    }

    protected void cancelTimeoutTimer(String str) {
        this.service.taskHandler.removeCallbacks(this.transferTimeoutAlarmRunnable);
    }

    public void uploadMapFile(OfflineMap offlineMap) {
        int i;
        synchronized (this.service) {
            try {
                try {
                    this.mapsListRequestTime = 0L;
                    this.currentMapUpload = offlineMap;
                    String[] strArrSplit = offlineMap.getFileNameLzm().replace(".lzm", "").split("_");
                    String str = strArrSplit[1] + "_" + strArrSplit[2] + "_" + strArrSplit[3] + "_" + strArrSplit[4];
                    byte[] bytes = str.getBytes(CharEncoding.UTF_8);
                    byte[] bArr = new byte[32];
                    for (int i2 = 0; i2 < 32; i2++) {
                        if (i2 < bytes.length) {
                            bArr[i2] = bytes[i2];
                        } else {
                            bArr[i2] = 0;
                        }
                    }
                    Log.i("MapFile", "sending map named:" + str);
                    File file = new File(this.service.getExternalFilesDir(null).toString(), this.currentMapUpload.getFileNameLzm());
                    if (!file.exists()) {
                        file = new File(this.service.getFilesDir(), this.currentMapUpload.getFileNameLzm());
                    }
                    this.currentMapUpload.setLocalLzmFile(file);
                    OfflineMap offlineMap2 = this.currentMapUpload;
                    offlineMap2.setLzmFileSize((int) offlineMap2.getLocalLzmFile().length());
                    this.mapFileStream = new FileInputStream(this.currentMapUpload.getLocalLzmFile());
                    byte[] bArr2 = new byte[1024];
                    char cGetCRC16 = 0;
                    do {
                        try {
                            i = this.mapFileStream.read(bArr2, 0, 1024);
                            for (int i3 = 0; i3 < i; i3++) {
                                cGetCRC16 = PackagedSegment.GetCRC16(cGetCRC16, bArr2[i3]);
                            }
                        } catch (IOException e) {
                            e.printStackTrace();
                        }
                    } while (i == 1024);
                    try {
                        this.mapFileStream.close();
                    } catch (NullPointerException e2) {
                        e2.printStackTrace();
                    }
                    this.mapFileStream = new FileInputStream(this.currentMapUpload.getLocalLzmFile());
                    this.currentMapUpload.setLzmFileCrc16(cGetCRC16);
                    this.currentMapUpload = offlineMap;
                    ByteBuffer byteBufferWrap = ByteBuffer.wrap(newPacket());
                    byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
                    byteBufferWrap.put(OutgoingCommands.MapFileReadyStart.byteValue());
                    byteBufferWrap.putInt(this.currentMapUpload.getLzmFileSize());
                    byteBufferWrap.putShort((short) this.currentMapUpload.getLzmFileCrc16());
                    byteBufferWrap.put(bArr, 0, 13);
                    this.outgoingMessageQue.add(byteBufferWrap.array());
                    ByteBuffer byteBufferWrap2 = ByteBuffer.wrap(newPacket());
                    byteBufferWrap2.put(OutgoingCommands.MapFileReadyEnd.byteValue());
                    byteBufferWrap2.put(bArr, 13, 19);
                    this.outgoingMessageQue.add(byteBufferWrap2.array());
                    postMessageQue();
                    this.service.taskHandler.postDelayed(this.fileUploadRequestTimeoutHandler, 40000L);
                    this.service.stopIdleTaskTimer();
                } catch (IOException e3) {
                    e3.printStackTrace();
                }
            } catch (UnsupportedEncodingException e4) {
                e4.printStackTrace();
            }
        }
    }

    public void sendNextPacket() throws IOException {
        this.service.taskHandler.removeCallbacks(this.fileUploadRequestTimeoutHandler);
        if (!isConnected()) {
            MapFileUploadProgressReceiver.postFileUploadFailed(this.service);
            this.service.startIdleTaskTimer();
            return;
        }
        this.service.stopIdleTaskTimer();
        try {
            byte[] bArrArray = newBigPacket().array();
            int length = bArrArray.length - 1;
            int i = this.mapFileStream.read(bArrArray, 1, length);
            int i2 = this.mapFileBytesSent + i;
            this.mapFileBytesSent = i2;
            if (i < length || i2 >= this.currentMapUpload.getLzmFileSize()) {
                bArrArray[0] = OutgoingCommands.MapFileEnd.byteValue();
                this.mapFileStream.close();
                this.currentMapUpload = null;
                this.mapFileBytesSent = 0;
                this.mapFileStream = null;
            } else {
                bArrArray[0] = OutgoingCommands.MapFileData.byteValue();
            }
            this.outgoingMessageQue.add(bArrArray);
            postMessageQue();
            if (bArrArray[0] != OutgoingCommands.MapFileEnd.byteValue()) {
                if (this.outgoingMessageQue.size() > 20) {
                    Log.i("MTU", "Map file sent bytes " + this.mapFileBytesSent + " queu size = " + this.outgoingMessageQue.size());
                    this.service.taskHandler.postDelayed(this.sendPacketRunnable, this.outgoingMessageQue.size());
                } else if (this.outgoingMessageQue.size() < 5) {
                    this.service.taskHandler.postDelayed(this.sendPacketRunnable, 10L);
                } else {
                    this.service.taskHandler.postDelayed(this.sendPacketRunnable, 40L);
                }
                float fElapsedRealtime = (SystemClock.elapsedRealtime() - this.mapUploadStartTime) / 1000.0f;
                MapFileUploadProgressReceiver.postMapFileUploadProgress(this.service, (int) ((this.mapFileBytesSent / this.currentMapUpload.getLzmFileSize()) * 100.0f), (int) ((fElapsedRealtime / this.mapFileBytesSent) * (this.currentMapUpload.getLzmFileSize() - this.mapFileBytesSent)), (int) fElapsedRealtime);
                return;
            }
            this.postMapSendingComplete = new Runnable() { // from class: com.lezyne.gpsally.services.LezyneCycleComputerDevice.28
                @Override // java.lang.Runnable
                public void run() throws IOException {
                    if (LezyneCycleComputerDevice.this.postMapSendingComplete != null) {
                        LezyneCycleComputerDevice.this.service.taskHandler.removeCallbacks(LezyneCycleComputerDevice.this.postMapSendingComplete);
                        LezyneCycleComputerDevice.this.postMapSendingComplete = null;
                    }
                    LezyneCycleComputerDevice.this.currentMapUpload = null;
                    try {
                        LezyneCycleComputerDevice.this.mapFileStream.close();
                    } catch (Exception unused) {
                    }
                    LezyneCycleComputerDevice.this.mapFileStream = null;
                    MapFileUploadProgressReceiver.postMapFileUploadFinished(LezyneCycleComputerDevice.this.service);
                }
            };
        } catch (IOException | NullPointerException e) {
            e.printStackTrace();
            MapFileUploadProgressReceiver.postFileUploadFailed(this.service);
            this.currentMapUpload = null;
            try {
                this.mapFileStream.close();
            } catch (Exception unused) {
            }
            this.mapFileStream = null;
        }
    }

    @Override // android.bluetooth.BluetoothGattCallback
    public void onMtuChanged(BluetoothGatt bluetoothGatt, int i, int i2) {
        Log.i("MTU", "onMtuChanged to " + i + "  with status " + i2);
        this.currentMtu = i - 3;
        this.blockMessageQueue = false;
    }

    public ByteBuffer newBigPacket() {
        byte[] bArr = new byte[this.currentMtu];
        for (int i = 0; i < this.currentMtu; i++) {
            bArr[i] = 0;
        }
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        return byteBufferWrap;
    }

    public ByteBuffer newMediumPacket() {
        if (this.currentMtu < 39) {
            return newBigPacket();
        }
        byte[] bArr = new byte[39];
        for (int i = 0; i < 39; i++) {
            bArr[i] = 0;
        }
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArr);
        byteBufferWrap.order(ByteOrder.LITTLE_ENDIAN);
        return byteBufferWrap;
    }

    public byte[] newPacket() {
        byte[] bArr = new byte[20];
        for (int i = 0; i < 20; i++) {
            bArr[i] = 0;
        }
        return bArr;
    }

    public void getMapFileList(boolean z) {
        if (!z && SystemClock.elapsedRealtime() - this.mapsListRequestTime.longValue() < 300000) {
            this.service.onMapFileListDownloaded(true);
            return;
        }
        if (!isWaiting()) {
            this.service.onMapFileListDownloaded(true);
            return;
        }
        OfflineMap.INSTANCE.removeDeviceInformation(this.service);
        byte[] bArrNewPacket = newPacket();
        bArrNewPacket[0] = OutgoingCommands.MapFileListRequest.byteValue();
        this.outgoingMessageQue.add(bArrNewPacket);
        postMessageQue();
        this.service.taskHandler.postDelayed(this.getMapListTimeout, 10000L);
        this.mapsListRequestTime = Long.valueOf(SystemClock.elapsedRealtime());
    }

    private void handleMapFileData(ByteBuffer byteBuffer) {
        OfflineMap.INSTANCE.addOnDeviceMap(this.service.getApplicationContext(), new OfflineMap(byteBuffer));
    }

    public void deleteMapFile(OfflineMap offlineMap) {
        if (this.mapFileToDelete != null) {
            throw new IllegalStateException("Deleteing pile up");
        }
        this.mapFileToDelete = offlineMap;
        byte[] bArrNewPacket = newPacket();
        ByteBuffer byteBufferWrap = ByteBuffer.wrap(bArrNewPacket);
        byteBufferWrap.put(OutgoingCommands.MapFileDelete.byteValue());
        byteBufferWrap.put(offlineMap.getDeviceNameOnGps());
        this.outgoingMessageQue.add(bArrNewPacket);
        postMessageQue();
        this.service.taskHandler.postDelayed(this.deleteMapTimeout, 20000L);
        this.mapsListRequestTime = 0L;
    }
}