import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import java.util.*;

// args: startAddr endAddr lo hi   -> list instructions in [start,end) with a scalar operand in [lo,hi]
public class FindImm extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        Address s = sp.getAddress(new java.math.BigInteger(a[0].replace("0x",""),16).longValue()), e = sp.getAddress(new java.math.BigInteger(a[1].replace("0x",""),16).longValue());
        long lo = new java.math.BigInteger(a[2].replace("0x",""),16).longValue(), hi = new java.math.BigInteger(a[3].replace("0x",""),16).longValue();
        InstructionIterator it = currentProgram.getListing().getInstructions(new AddressSet(s, e), true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            for (int i = 0; i < ins.getNumOperands(); i++) {
                for (Object o : ins.getOpObjects(i)) {
                    if (o instanceof Scalar) {
                        long v = ((Scalar) o).getUnsignedValue();
                        if (v >= lo && v <= hi) {
                            Function f = currentProgram.getFunctionManager().getFunctionContaining(ins.getAddress());
                            println(ins.getAddress() + "  " + ins + "   in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "???"));
                        }
                    }
                }
            }
        }
    }
}
