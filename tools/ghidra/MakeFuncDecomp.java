import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;

// args: outfile start end -> disassemble the range, create functions at each given start, decompile
public class MakeFuncDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        try (PrintWriter w = new PrintWriter(new FileWriter(a[0]))) {
            for (int i = 1; i < a.length; i++) {
                Address ad = sp.getAddress(new java.math.BigInteger(a[i].replace("0x",""),16).longValue());
                disassemble(ad);
                Function f = getFunctionAt(ad);
                if (f == null) f = createFunction(ad, null);
                if (f == null) { w.println("// could not create function at " + ad); continue; }
                DecompileResults r = d.decompileFunction(f, 90, monitor);
                w.println("\n// === " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses());
                if (r.decompileCompleted()) w.println(r.getDecompiledFunction().getC()); else w.println("// failed");
            }
        }
    }
}
