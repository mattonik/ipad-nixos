import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;

// args: outfile addr [addr...]  -> decompile the function containing/at each addr
public class DecompTo extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new FileWriter(a[0]))) {
            for (int i = 1; i < a.length; i++) {
                Address ad = sp.getAddress(new java.math.BigInteger(a[i].replace("0x",""),16).longValue());
                Function f = currentProgram.getFunctionManager().getFunctionContaining(ad);
                if (f == null) { w.println("// no function at " + a[i]); continue; }
                DecompileResults r = d.decompileFunction(f, 90, monitor);
                w.println("\n// === " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses());
                if (r.decompileCompleted()) w.println(r.getDecompiledFunction().getC());
                else w.println("// decompile failed");
            }
        }
    }
}
