import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
public class PrintRange extends GhidraScript {
 public void run() throws Exception {
  String[] a=getScriptArgs(); AddressSpace s=currentProgram.getAddressFactory().getDefaultAddressSpace();
  Address x=s.getAddress(new java.math.BigInteger(a[0],16).longValue());
  Address e=s.getAddress(new java.math.BigInteger(a[1],16).longValue());
  for(;x.compareTo(e)<=0;x=x.add(4)){disassemble(x); Instruction i=getInstructionAt(x); if(i!=null)println(i.getAddress()+" "+i);}
 }
}
