import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import java.math.BigInteger;

// args: startAddr endAddr   -> force Thumb, then disassemble and create a function at every PUSH {..., lr} prologue
// (for raw Cortex-R4 images such as the Broadcom dongle firmware, where auto-analysis does not find the Thumb code).
public class ThumbSweep extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        long s = new BigInteger(a[0].replace("0x", ""), 16).longValue(), e = new BigInteger(a[1].replace("0x", ""), 16).longValue();
        clearListing(sp.getAddress(s), sp.getAddress(e));
        Register t = currentProgram.getLanguage().getRegister("TMode");
        currentProgram.getProgramContext().setValue(t, sp.getAddress(s), sp.getAddress(e), BigInteger.ONE);
        int made = 0;
        for (long p = s; p < e - 4; p += 2) {
            Address ad = sp.getAddress(p);
            int h = getShort(ad) & 0xffff;
            boolean push = (h & 0xff00) == 0xb500 || ((h == 0xe92d) && ((getShort(ad.add(2)) & 0x4000) != 0));
            if (!push) continue;
            if (getFunctionContaining(ad) != null) continue;
            disassemble(ad);
            if (createFunction(ad, null) != null) made++;
        }
        println("created functions: " + made);
    }
}
