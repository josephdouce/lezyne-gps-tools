package com.lezyne.gpsally.tools;

import android.content.Context;
import android.util.Base64;
import com.garmin.fit.MessageIndex;
import com.google.android.gms.maps.model.LatLng;
import com.google.common.base.Ascii;
import com.lezyne.gpsally.Segment;
import dbg.Log;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.Charset;
import java.util.List;
import org.apache.commons.lang3.CharEncoding;

/* loaded from: classes2.dex */
public class PackagedSegment implements Serializable {
    static final char[] crc_table = {0, 52225, 55297, 5120, 61441, 15360, 10240, 58369, 40961, 27648, 30720, 46081, 20480, 39937, 34817, 17408};
    public byte[] buffer;
    public char crc;
    public short size;

    public static char GetCRC16(char c, byte b) {
        char[] cArr = crc_table;
        char c2 = (char) ((((char) ((c >>> 4) & MessageIndex.MASK)) ^ cArr[c & 15]) ^ cArr[b & Ascii.SI]);
        return (char) ((((char) ((c2 >>> 4) & MessageIndex.MASK)) ^ cArr[c2 & 15]) ^ cArr[(b >>> 4) & 15]);
    }

    static String segmentFileName(long j, Context context) {
        return new Settings(context).username() + "strava" + j;
    }

    public void saveFile(Context context, Segment segment) {
        try {
            FileOutputStream fileOutputStreamOpenFileOutput = context.openFileOutput(segmentFileName(segment.getId(), context), 0);
            ObjectOutputStream objectOutputStream = new ObjectOutputStream(fileOutputStreamOpenFileOutput);
            objectOutputStream.writeObject(this);
            objectOutputStream.close();
            fileOutputStreamOpenFileOutput.close();
            segment.setSegmentCrcValue(context, (short) this.crc);
            Log.i("Rides", "Wrote segment " + segment.getId() + " had crc " + ((int) this.crc));
        } catch (IOException unused) {
            Log.e("Rides", "Failed to write segment data");
        }
    }

    public static PackagedSegment fromFile(Context context, long j) {
        try {
            FileInputStream fileInputStreamOpenFileInput = context.openFileInput(segmentFileName(j, context));
            ObjectInputStream objectInputStream = new ObjectInputStream(fileInputStreamOpenFileInput);
            PackagedSegment packagedSegment = (PackagedSegment) objectInputStream.readObject();
            objectInputStream.close();
            fileInputStreamOpenFileInput.close();
            return packagedSegment;
        } catch (IOException | ClassNotFoundException unused) {
            Log.e("Rides", "Failed to read segment data");
            return null;
        }
    }

    /* JADX WARN: Multi-variable type inference failed */
    public static PackagedSegment create(Segment segment, Context context) {
        short komTimeInSeconds;
        byte[] bArrDecode;
        byte[] bArrDecode2;
        PackagedSegment packagedSegment = new PackagedSegment();
        ByteBuffer byteBufferAllocate = ByteBuffer.allocate(10000);
        byteBufferAllocate.order(ByteOrder.LITTLE_ENDIAN);
        byteBufferAllocate.putInt((int) segment.getDistance());
        double d = segment.getStartLocation().latitude;
        double d2 = segment.getStartLocation().longitude;
        byteBufferAllocate.putInt((int) (d * 1.1930464E7d));
        byteBufferAllocate.putInt((int) (d2 * 1.1930464E7d));
        double d3 = segment.getEndLocation().latitude;
        double d4 = segment.getEndLocation().longitude;
        byteBufferAllocate.putInt((int) (d3 * 1.1930464E7d));
        byteBufferAllocate.putInt((int) (d4 * 1.1930464E7d));
        byteBufferAllocate.putShort((short) (segment.getAverageGrade() != 0.0f ? segment.getAverageGrade() * 255.0d : 0.0d));
        short s = (short) 0.0d;
        byteBufferAllocate.putShort(s);
        byteBufferAllocate.putShort(s);
        byteBufferAllocate.putShort(s);
        byte[] bytes = segment.getName().getBytes(Charset.forName(CharEncoding.UTF_8));
        int length = bytes.length;
        if (length > 19) {
            length = 19;
        }
        byteBufferAllocate.put((byte) length);
        byteBufferAllocate.put(bytes, 0, length);
        List<LatLng> listDecodePolyline = MapTool.decodePolyline(segment.getPolylineString());
        byte[] bArrEncodeBinaryPolyline = MapTool.encodeBinaryPolyline(listDecodePolyline, listDecodePolyline.size() * 6);
        int length2 = bArrEncodeBinaryPolyline.length;
        if (length2 > 2000) {
            length2 = 2000;
        }
        byteBufferAllocate.putShort((short) length2);
        byteBufferAllocate.put(bArrEncodeBinaryPolyline, 0, length2);
        byteBufferAllocate.putShort(segment.getPrTimeInSeconds() != 0 ? (short) segment.getPrTimeInSeconds() : (short) 0);
        try {
            komTimeInSeconds = (short) segment.getKomTimeInSeconds();
        } catch (NullPointerException unused) {
            komTimeInSeconds = 0;
        }
        byteBufferAllocate.putShort(komTimeInSeconds);
        boolean isHazardous = segment.getIsHazardous();
        int i = isHazardous;
        if (segment.getAverageGrade() < -0.25d) {
            i = (isHazardous ? 1 : 0) | 2;
        }
        byteBufferAllocate.putShort((short) i);
        try {
            bArrDecode = Base64.decode(segment.getCompressedStreamDistance(), 3);
            if (segment.getGoalCompare(context) == 0) {
                bArrDecode2 = Base64.decode(segment.getCompressedPrStreamTime(), 3);
            } else {
                bArrDecode2 = Base64.decode(segment.getCompressedKomStreamTime(), 3);
            }
        } catch (NullPointerException unused2) {
            bArrDecode = new byte[0];
            bArrDecode2 = new byte[0];
        }
        short length3 = (short) bArrDecode.length;
        short length4 = (short) bArrDecode2.length;
        int i2 = length3 + length4;
        int i3 = (i2 + 3) >> 2;
        short s2 = (short) (i3 + 1);
        int i4 = (i3 << 2) - i2;
        byteBufferAllocate.putShort(s2);
        byteBufferAllocate.putShort(length3);
        if (length3 != 0) {
            byteBufferAllocate.put(bArrDecode, 0, length3);
        }
        byteBufferAllocate.putShort(length4);
        if (length4 != 0) {
            byteBufferAllocate.put(bArrDecode2, 0, length4);
        }
        for (int i5 = 0; i5 < i4; i5++) {
            byteBufferAllocate.put((byte) 0);
        }
        short sPosition = (short) byteBufferAllocate.position();
        byteBufferAllocate.putShort(sPosition);
        char cGetCRC16 = 0;
        for (int i6 = 0; i6 < byteBufferAllocate.position(); i6++) {
            cGetCRC16 = GetCRC16(cGetCRC16, byteBufferAllocate.get(i6));
        }
        short s3 = (short) cGetCRC16;
        byteBufferAllocate.putShort(s3);
        segment.setSegmentCrcValue(context, s3);
        Log.i("Rides", "Wrote CRC value " + ((int) cGetCRC16));
        packagedSegment.buffer = byteBufferAllocate.array();
        packagedSegment.crc = cGetCRC16;
        packagedSegment.size = (short) (sPosition + 4);
        return packagedSegment;
    }
}